"""Layered depth meshes with z-buffer, source UVs and reconstruction provenance.

Hidden background is completed once per depth layer. Original defect pixels are
never inpainted in their own layer; only original visible pixels create labels.
"""
import math
import numpy as np
from camera import points, polygon_area


VERTEX = '''#version 330
in vec3 position;
in vec2 source_uv;
in float risk;
uniform mat3 rotation;
uniform vec3 eye;
uniform vec4 intrinsics;
uniform vec2 viewport_size;
out vec2 uv;
out float uncertainty;
void main() {
    vec3 q = rotation * (position-eye);
    vec2 pixel = intrinsics.xy*q.xy + intrinsics.zw*q.z;
    float zn=.05, zf=20.;
    gl_Position=vec4(2.*pixel.x/viewport_size.x-q.z,
                     q.z-2.*pixel.y/viewport_size.y,
                     (zf+zn)/(zf-zn)*q.z-2.*zf*zn/(zf-zn), q.z);
    uv=source_uv; uncertainty=risk;
}
'''
FRAGMENT = '''#version 330
uniform sampler2D photo;
uniform sampler2D layer_mask;
uniform vec4 region;
uniform bool isolate;
in vec2 uv;
in float uncertainty;
layout(location=0) out vec4 color;
layout(location=1) out vec4 provenance;
void main() {
    vec2 mask=texture(layer_mask,uv).rg;
    if(mask.r<.5) discard;
    if(isolate && (uv.x<region.x || uv.y<region.y || uv.x>=region.z || uv.y>=region.w)) discard;
    if(isolate && mask.g>.5) discard;
    color=vec4(texture(photo,uv).rgb,1.);
    provenance=vec4(uv,uncertainty,mask.g>.5 ? 2. : 1.);
}
'''


def motion_pose(crop, source_size, output_size, t, duration, seed, strength, focus_depth, crop_scale=.86):
    sw,sh=source_size;w,h=output_size
    x,y,cw,ch=crop
    # Reserve source border for camera motion; texture outside the photo is unknown.
    cw*=crop_scale;ch=cw*h/w
    cx=np.clip(x+crop[2]/2,cw/2,sw-cw/2)
    cy=np.clip(y+crop[3]/2,ch/2,sh-ch/2)
    x=float(cx-cw/2);y=float(cy-ch/2)
    phase=(seed%1000)*.017
    angle=2*math.pi*t/max(duration,1)
    # Bound screen-space parallax at close-up: zoom must not magnify hidden strips.
    travel_scale=cw/min(sw,sh*w/h)
    eye=np.array([strength*.025*travel_scale*math.sin(angle+phase),
                  strength*.01*travel_scale*math.sin(angle*.7+phase),
                  strength*.01*travel_scale*math.sin(angle*.5)],dtype='f4')
    yaw=float(eye[0]/focus_depth)+.002*math.sin(9.7*t+phase)*strength
    pitch=-float(eye[1]/focus_depth)+.001*math.sin(12.3*t)*strength
    roll=strength*(.006*math.sin(.7*t+phase)+.0007*math.sin(15.7*t))
    ca,sa,cb,sb,cc,sc=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch),math.cos(roll),math.sin(roll)
    rotation=np.array([[cc,-sc,0],[sc,cc,0],[0,0,1]]) @ np.array([[ca,0,sa],[0,1,0],[-sa,0,ca]]) @ np.array([[1,0,0],[0,cb,-sb],[0,sb,cb]])
    focal=max(sw,sh)*1.2
    intrinsics=np.array([focal*w/cw,focal*h/ch,(sw/2-x)*w/cw,(sh/2-y)*h/ch])
    return {'eye':eye.tolist(),'rotation':rotation.tolist(),'intrinsics':intrinsics.tolist(),
            'crop_xywh':[x,y,cw,ch]}


def mask_bbox(mask):
    yy,xx=np.nonzero(mask)
    if not len(xx): return None
    return [int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]


def extend_nearest(values,valid):
    """Extend only geometry into hidden portions of a layer, not object RGB."""
    import cv2
    if valid.all():return values.copy()
    _,labels=cv2.distanceTransformWithLabels((~valid).astype('uint8'),cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
    lookup=np.zeros(int(labels.max())+1,dtype='f4')
    lookup[labels[valid]]=values[valid]
    return lookup[labels]


def depth_layers(image,near,protected):
    import cv2
    rgb=np.asarray(image)
    gh,gw=near.shape
    labels=np.minimum((near*3).astype('uint8'),2)
    layers=[]
    # Each layer completes only the regions originally hidden behind nearer layers.
    for label in range(3):
        valid=labels==label
        if not valid.any():continue
        coverage=labels>=label if layers else np.ones_like(valid)
        hidden=labels>label
        znear=extend_nearest(near,valid)
        # No cross-layer interpolated depth walls: each mesh has continuous extrapolated depth.
        texture=rgb.copy()
        completed_mask=hidden.copy()
        if hidden.any():
            completed_mask=cv2.dilate(hidden.astype('uint8'),np.ones((7,7),np.uint8))>0
            # Keep protected original pixels in their own layer intact, including bbox corners.
            completed_mask[(protected>0)&valid]=False
            small=cv2.resize(rgb,(gw,gh),interpolation=cv2.INTER_AREA)
            completed=cv2.inpaint(small,(completed_mask*255).astype('uint8'),7,cv2.INPAINT_TELEA)
            full=cv2.resize(completed,image.size,interpolation=cv2.INTER_CUBIC)
            # Expanded mask is only the inpainting context. Preserve every known
            # pixel of this layer; otherwise stationary views acquire fake halos.
            unknown=cv2.resize(hidden.astype('uint8'),image.size,interpolation=cv2.INTER_NEAREST)>0
            texture[unknown]=full[unknown]
        masks=np.stack([coverage.astype('uint8')*255,hidden.astype('uint8')*255],axis=-1)
        layers.append((texture,masks,znear))
    return layers


class DepthRenderer:
    def __init__(self,image,near,protected,objects,output_size):
        import moderngl
        self.gl=moderngl
        self.ctx=moderngl.create_standalone_context(require=330)
        self.resources=[]
        self.size=output_size;self.source_size=image.size;self.objects=objects
        self.near=near
        sw,sh=image.size;gh,gw=near.shape
        self.focus_depth=float(np.median(1/(.35+.65*near)))
        uvx,uvy=np.meshgrid(np.linspace(0,1,gw),np.linspace(0,1,gh))
        focal=max(sw,sh)*1.2
        rows,cols=np.meshgrid(np.arange(gh-1),np.arange(gw-1),indexing='ij')
        a=(rows*gw+cols).ravel()
        triangles=np.stack([a,a+gw,a+1,a+1,a+gw,a+gw+1],axis=1).astype('u4').ravel()
        self.program=self.keep(self.ctx.program(vertex_shader=VERTEX,fragment_shader=FRAGMENT))
        self.ibo=self.keep(self.ctx.buffer(triangles.tobytes()))
        self.layers=[]
        for texture,masks,layer_near in depth_layers(image,near,protected):
            z=1/(.35+.65*layer_near)
            xyz=np.stack([(uvx*sw-sw/2)/focal*z,(uvy*sh-sh/2)/focal*z,z],axis=-1)
            gy,gx=np.gradient(layer_near)
            risk=np.clip(np.maximum(abs(gx),abs(gy))/.035,0,1)
            risk[protected>0]=0
            vertices=np.dstack([xyz,uvx,uvy,risk]).astype('f4')
            vbo=self.keep(self.ctx.buffer(vertices.tobytes()))
            vao=self.keep(self.ctx.vertex_array(self.program,[(vbo,'3f 2f 1f','position','source_uv','risk')],self.ibo))
            tex=self.keep(self.ctx.texture(image.size,3,texture.tobytes()))
            tex.filter=(moderngl.LINEAR,moderngl.LINEAR)
            tex.repeat_x=False;tex.repeat_y=False
            mask_tex=self.keep(self.ctx.texture((gw,gh),2,masks.tobytes()))
            mask_tex.filter=(moderngl.NEAREST,moderngl.NEAREST)
            mask_tex.repeat_x=False;mask_tex.repeat_y=False
            self.layers.append((vao,tex,mask_tex))
        self.program['photo']=0;self.program['layer_mask']=1
        self.color=self.keep(self.ctx.texture(output_size,4,dtype='f1'))
        self.provenance=self.keep(self.ctx.texture(output_size,4,dtype='f4'))
        self.depth=self.keep(self.ctx.depth_renderbuffer(output_size))
        self.fbo=self.keep(self.ctx.framebuffer([self.color,self.provenance],self.depth))
        self.program['viewport_size']=output_size
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.depth_func='<='
        self.metadata={'renderer':self.ctx.info['GL_RENDERER'],'grid_size':[gw,gh],
                       'relative_depth_mapping':'z = 1 / (0.35 + 0.65 * normalized_inverse_depth)',
                       'source_focal_px':focal,'rgb_policy':'original visible texture; hidden background completed per layer by OpenCV Telea; reconstructed pixels excluded from labels',
                       'geometry_policy':'3 stabilized depth surfaces; whole bbox belongs to one surface; reconstructed source pixels flagged',
                       'depth_layer_count':len(self.layers)}

    def keep(self,resource):
        self.resources.append(resource);return resource

    def draw(self,pose,region=None,read_rgb=True):
        self.fbo.use();self.fbo.clear(0,0,0,0,depth=1.)
        self.program['rotation'].write(np.asarray(pose['rotation'],dtype='f4').T.tobytes())
        self.program['eye']=tuple(pose['eye'])
        self.program['intrinsics']=tuple(pose['intrinsics'])
        self.program['isolate']=region is not None
        self.program['region']=tuple(region or [0,0,1,1])
        for vao,tex,mask_tex in self.layers:
            tex.use(0);mask_tex.use(1);vao.render()
        w,h=self.size
        uv=np.frombuffer(self.provenance.read(),dtype='f4').reshape(h,w,4)[::-1].copy()
        rgb=None
        if read_rgb:
            rgb=np.frombuffer(self.color.read(),dtype=np.uint8).reshape(h,w,4)[::-1,:,:3].copy()
        return rgb,uv

    def projected_corners(self,box,pose):
        sw,sh=self.source_size;gh,gw=self.near.shape
        x1,y1,x2,y2=box
        # Protected core is planar: use its median depth, including overlapping regions.
        ix=int(np.clip((x1+x2)/2/sw*(gw-1),0,gw-1))
        iy=int(np.clip((y1+y2)/2/sh*(gh-1),0,gh-1))
        z=1/(.35+.65*self.near[iy,ix])
        focal=max(sw,sh)*1.2
        corners=np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],dtype=float)
        xyz=np.c_[(corners-np.array([sw/2,sh/2]))/focal*z,np.full(4,z)]
        q=(xyz-np.array(pose['eye']))@np.array(pose['rotation']).T
        fx,fy,cx,cy=pose['intrinsics']
        return (q[:,:2]/q[:,2:]*[fx,fy]+[cx,cy]).tolist()

    def render(self,pose,annotate=True):
        rgb,uv=self.draw(pose)
        valid=uv[:,:,3]>.5
        original=valid&(uv[:,:,3]<1.5)
        self.last_original_mask=original
        self.last_reconstructed_fraction=float((~original&valid).mean())
        if not valid.all():
            raise RuntimeError('Камера открыла область вне фото. Уменьшите силу параллакса или используйте более широкий исходник.')
        if not annotate:return rgb,[]
        w,h=self.size;sw,sh=self.source_size
        annotations=[]
        for obj in self.objects:
            x1,y1,x2,y2=obj['bbox']
            region=[x1/sw,y1/sh,x2/sw,y2/sh]
            visible=original&(uv[:,:,0]>=region[0])&(uv[:,:,0]<region[2])&(uv[:,:,1]>=region[1])&(uv[:,:,1]<region[3])
            visible_pixels=int(visible.sum())
            # Isolated pass measures in-frame object area before occlusion by other geometry.
            _,isolated=self.draw(pose,region,read_rgb=False)
            unoccluded=int((isolated[:,:,3]>.5).sum())
            corners=self.projected_corners(obj['bbox'],pose)
            full_area=polygon_area(corners)
            fraction=min(1.,visible_pixels/max(full_area,unoccluded,1))
            bbox=mask_bbox(visible)
            uncertain=float((uv[:,:,2][visible]>.3).mean()) if visible_pixels else 0.
            eligible=visible_pixels>=16 and fraction>=.95 and uncertain<=.01
            annotations.append({'object_id':obj['object_id'],'label':obj['label'],
                'bbox_xyxy_px':bbox,'bbox':[bbox[0]/w,bbox[1]/h,bbox[2]/w,bbox[3]/h] if bbox else None,
                'visible':bbox is not None,'visible_pixels':visible_pixels,'visible_fraction':fraction,
                'occluded_fraction':max(0.,1-visible_pixels/max(unoccluded,1)) if unoccluded else 0.,
                'truncated':any(x<0 or x>w or y<0 or y>h for x,y in corners),
                'projected_source_bbox_polygon':corners,'uncertain_fraction':uncertain,
                'keyframe_eligible':eligible,
                'quality_score':fraction*math.sqrt(visible_pixels/(w*h)) if eligible else 0.})
        return rgb,annotations

    def close(self):
        for resource in reversed(self.resources):resource.release()
        self.resources=[]
        self.ctx.release()
