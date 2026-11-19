"""Seeded, intermittent capture degradation; never changes annotation geometry."""
import math
import numpy as np
from PIL import Image, ImageFilter


class CaptureEffects:
    def __init__(self, config):
        self.config=config
        self.previous=None
        self.activity=0.

    def apply(self, frame, index, crop, matrix=None, pose=None):
        c=self.config;fps=c['fps'];w,h=c['width'],c['height']
        x,y,cw,ch=crop
        # Track several fixed source points: catches zoom/rotation as well as translation.
        if self.previous is None:
            self.probes=np.array([[x+cw*u,y+ch*v,1.] for u,v in ((.2,.2),(.8,.2),(.5,.5),(.2,.8),(.8,.8))])
        if matrix is not None:
            q=self.probes@np.asarray(matrix).T;points=q[:,:2]/q[:,2:]
        elif pose is not None:
            # Crop motion remains the dominant signal; eye/rotation capture depth-only motion.
            points=(self.probes[:,:2]-[x,y])*[w/cw,h/ch]
            eye=np.asarray(pose['eye']);rotation=np.asarray(pose['rotation'])
            points+=(eye[:2]+rotation[:2,2])*w
        else:points=(self.probes[:,:2]-[x,y])*[w/cw,h/ch]
        delta=np.zeros_like(points) if self.previous is None else points-self.previous
        self.previous=points
        speed=float(np.sqrt((delta**2).sum(axis=1)).mean())*fps/w
        self.activity+=(min(1.,speed/.18)-self.activity)*(1-math.exp(-1/(fps*.18)))
        t=index/fps;phase=(c['seed']%10000)*.173
        burst=max(0.,math.sin(t*1.13+phase))**4
        gate=burst*self.activity if self.activity>.015 else 0.
        blur=c['blur_strength']*gate*4*w/1280
        sigma=c['noise_strength']*gate*9
        info={'blur_radius_px':blur,'noise_sigma_255':sigma,'motion_activity':self.activity}
        if blur<.01 and sigma<.01:return frame,info
        im=frame if isinstance(frame,Image.Image) else Image.fromarray(frame)
        if blur>=.01:
            # Mild focus softness plus a short exposure streak along dominant image motion.
            im=im.filter(ImageFilter.GaussianBlur(blur*.35))
            direction=delta[np.argmax((delta**2).sum(axis=1))]
            norm=np.linalg.norm(direction)
            direction=direction/max(norm,1e-9)*blur
            # Edge padding avoids black borders during convolution.
            pad=max(2,math.ceil(blur)+2)
            padded=Image.fromarray(np.pad(np.asarray(im),((pad,pad),(pad,pad),(0,0)),mode='edge'))
            acc=np.zeros((h,w,3),dtype=np.float32)
            for offset in np.linspace(-1,1,5):
                shifted=padded.transform((w,h),Image.Transform.AFFINE,(1,0,pad+offset*direction[0],0,1,pad+offset*direction[1]),Image.Resampling.BILINEAR)
                acc+=np.asarray(shifted,dtype=np.float32)/5
        else:acc=np.asarray(im,dtype=np.float32)
        if sigma>=.01:
            rng=np.random.default_rng(np.random.SeedSequence([c['seed'],index,731]))
            # Mostly luminance noise, slightly stronger in shadows; no coloured TV static.
            shadow=1.15-.5*acc.mean(axis=2,keepdims=True)/255
            acc+=rng.normal(0,sigma,(h,w,1)).astype(np.float32)*shadow
        return np.clip(acc,0,255).astype(np.uint8),info
