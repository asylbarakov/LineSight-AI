"""Projective virtual camera. A single plane, not inferred scene depth."""
import math
import numpy as np


def points(matrix, polygon):
    p = np.c_[np.asarray(polygon), np.ones(len(polygon))] @ matrix.T
    return p[:, :2] / p[:, 2:]


def drone_matrix(crop, size, output, t, seed, strength=1, attitude=None):
    x, y, cw, ch = crop
    w, h = output
    phase = (seed % 1000) * .017
    # Low-frequency gimbal drift plus small band-limited vibration, in real seconds.
    yaw = strength*(.12*math.sin(.39*t+phase) + .003*math.sin(9.7*t+phase))
    pitch = strength*(.07*math.sin(.31*t+1+phase) + .002*math.sin(12.3*t))
    roll = strength*(.018*math.sin(.61*t+phase) + .0015*math.sin(15.7*t))
    if attitude is not None:
        yaw,pitch,roll=map(float,attitude)
    cy, sy, cp, sp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    rotation = np.array([[cr,-sr,0],[sr,cr,0],[0,0,1]]) @ np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]) @ np.array([[1,0,0],[0,cp,-sp],[0,sp,cp]])
    k = np.array([[w,0,w/2],[0,w,h/2],[0,0,1.]])
    base = np.array([[w/cw,0,-x*w/cw],[0,h/ch,-y*h/ch],[0,0,1.]])
    forward = k @ rotation @ np.linalg.inv(k) @ base
    inverse = np.linalg.inv(forward)
    corners = points(inverse, [(0,0),(w,0),(w,h),(0,h)])
    # Fit the entire sampled quadrilateral inside the source; no black borders/inpainting.
    low, high = corners.min(axis=0), corners.max(axis=0)
    iw, ih = size
    scale = min(1., (iw-2)/(high[0]-low[0]), (ih-2)/(high[1]-low[1]))
    center = (low+high)/2
    span = (high-low)*scale
    target = np.clip(center, span/2+1, np.array([iw,ih])-span/2-1)
    adjust = np.array([[scale,0,target[0]-scale*center[0]], [0,scale,target[1]-scale*center[1]],[0,0,1.]])
    inverse = adjust @ inverse
    inverse /= inverse[2,2]
    return np.linalg.inv(inverse), inverse


def polygon_area(poly):
    if len(poly)<3: return 0.
    p=np.asarray(poly)
    return float(abs(np.dot(p[:,0],np.roll(p[:,1],1))-np.dot(p[:,1],np.roll(p[:,0],1)))/2)


def project(box, matrix, output):
    w,h=output
    x1,y1,x2,y2=box
    polygon=points(matrix,[(x1,y1),(x2,y1),(x2,y2),(x1,y2)]).tolist()
    clipped=polygon
    for axis,edge,sign in [(0,0,1),(0,w,-1),(1,0,1),(1,h,-1)]:
        result=[]
        for a,b in zip(clipped,clipped[1:]+clipped[:1]):
            inside_a=(a[axis]-edge)*sign>=0
            inside_b=(b[axis]-edge)*sign>=0
            if inside_a: result.append(a)
            if inside_a != inside_b:
                ratio=(edge-a[axis])/(b[axis]-a[axis])
                result.append([a[j]+ratio*(b[j]-a[j]) for j in range(2)])
        clipped=result
    area=polygon_area(clipped)
    fraction=min(1.,area/max(polygon_area(polygon),1e-12))
    bbox=None
    if area>1e-9:
        p=np.asarray(clipped);bbox=[float(p[:,0].min()),float(p[:,1].min()),float(p[:,0].max()),float(p[:,1].max())]
    return {'polygon_xy_px':polygon, 'visible_polygon_xy_px':clipped,
            'bbox_xyxy_px':bbox, 'bbox':[bbox[0]/w,bbox[1]/h,bbox[2]/w,bbox[3]/h] if bbox else None,
            'visible':bbox is not None,'visible_fraction':fraction,'truncated':0<fraction<.999999,
            'quality_score':fraction*math.sqrt(area/(w*h))}
