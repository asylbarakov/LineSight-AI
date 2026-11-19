"""Seeded inspection flights: timed maneuvers, C2 motion, independent camera axes."""
import math
import numpy as np


def _tangents(times, values):
    """Inertial through-velocities: a new maneuver does not brake every axis to zero."""
    dt=np.diff(times)
    slopes=np.diff(values,axis=0)/dt[:,None]
    velocity=np.zeros_like(values)
    for i in range(1,len(values)-1):
        velocity[i]=.75*(values[i+1]-values[i-1])/(times[i+1]-times[i-1])
        # Zoom alone remains monotone to avoid an unwanted zoom pulse after a stop.
        left,right=slopes[i-1,2],slopes[i,2]
        velocity[i,2]=.65*2*left*right/(left+right) if left*right>0 else 0.
    return velocity


def interpolate(times, values, velocity, t):
    i=min(max(int(np.searchsorted(times,t,side='right'))-1,0),len(times)-2)
    dt=times[i+1]-times[i]
    u=float(np.clip((t-times[i])/dt,0,1))
    # Quintic Hermite with prescribed positions/velocities and zero acceleration at knots.
    p0,p1=values[i],values[i+1]
    v0,v1=velocity[i]*dt,velocity[i+1]*dt
    delta=p1-p0
    a3=10*delta-6*v0-4*v1
    a4=-15*delta+8*v0+7*v1
    a5=6*delta-3*v0-3*v1
    return p0+v0*u+a3*u**3+a4*u**4+a5*u**5,i


def make_flight(size, objects, duration, seed, profile='calm'):
    iw,ih=size;base=min(iw,ih*16/9)
    rng=np.random.default_rng(seed)
    # cx,cy,log(crop width), yaw,pitch,roll. Positions use original image pixels.
    state=np.array([iw*rng.uniform(.3,.7),ih*rng.uniform(.3,.7),math.log(base*rng.uniform(.5,.72)),0.,0.,0.])
    target_order=rng.permutation(len(objects)).tolist()
    capacity=max(1,int(duration/6))
    visits=target_order[:capacity]
    count=max(2,round(duration/rng.uniform(5,7)))
    count=max(count,len(visits)+1)
    # The maneuver set covers independent translation, yaw, pitch, and zoom.
    actions=[str(x) for x in rng.permutation(['lateral','rise','yaw_sweep','tilt_sweep','approach','recede'])]
    while len(actions)<count:actions.append(str(rng.choice(['lateral','rise','hover','approach','recede','diagonal'])))
    actions=actions[:count]
    slots=sorted(rng.choice(np.arange(count),size=len(visits),replace=False).tolist())
    inspection_slots=dict(zip(slots,visits))
    durations=rng.uniform(4.,9.,count)
    for i in inspection_slots:durations[i]*=1.15
    durations=durations/durations.sum()*duration
    times=np.r_[0.,np.cumsum(durations)]
    states=[];events=[]

    def bounded(s):
        cw=float(np.clip(math.exp(s[2]),base*.28,base*.88));ch=cw*9/16
        s=s.copy();s[0]=np.clip(s[0],cw/2,iw-cw/2);s[1]=np.clip(s[1],ch/2,ih-ch/2);s[2]=math.log(cw)
        s[3]=np.clip(s[3],-.105,.105);s[4]=np.clip(s[4],-.065,.065)
        return s

    state=bounded(state);states.append(state.copy())
    for i,action in enumerate(actions):
        next_state=state.copy();direction=float(rng.choice([-1,1]))
        if i in inspection_slots:
            obj=objects[inspection_slots[i]];x1,y1,x2,y2=obj['bbox']
            cw=np.clip(max((x2-x1)*rng.uniform(2.5,3.6),(y2-y1)*16/9*rng.uniform(2.5,3.6)),base*.3,base*.78)
            # Offset framing lets the defect pass across the view rather than stay locked in the centre.
            next_state[:3]=[(x1+x2)/2+cw*rng.uniform(-.12,.12),
                            (y1+y2)/2+cw*9/16*rng.uniform(-.1,.1),math.log(cw)]
            next_state[3:5]=[rng.uniform(-.045,.045),rng.uniform(-.03,.03)]
            action='inspection_pass'
        elif action in ('lateral','diagonal'):
            next_state[0]+=direction*iw*rng.uniform(.12,.28)
            next_state[1]+=ih*rng.uniform(-.12,.12)
            next_state[3]+=rng.uniform(-.025,.025)
            next_state[2]+=rng.uniform(-.12,.12)
        elif action=='rise':
            next_state[1]+=direction*ih*rng.uniform(.12,.25)
            next_state[0]+=iw*rng.uniform(-.06,.06)
            next_state[4]+=rng.uniform(-.02,.02)
        elif action=='yaw_sweep':
            next_state[3]=direction*rng.uniform(.055,.095)
            # A stationary aircraft rotating around its vertical axis.
        elif action=='tilt_sweep':
            next_state[4]=direction*rng.uniform(.035,.06)
        elif action in ('approach','recede'):
            next_state[2]+=(-1 if action=='approach' else 1)*rng.uniform(.2,.4)
            next_state[0]+=iw*rng.uniform(-.07,.07)
            next_state[1]+=ih*rng.uniform(-.05,.05)
        elif action=='hover':
            next_state[0]+=iw*rng.uniform(-.008,.008)
            next_state[1]+=ih*rng.uniform(-.008,.008)
        next_state[5]=rng.uniform(-.004,.004) if profile=='calm' else rng.uniform(-.012,.012)
        state=bounded(next_state);states.append(state.copy())
        events.append({'start_s':float(times[i]),'end_s':float(times[i+1]),'maneuver':action,
                       'object_id':objects[inspection_slots[i]].get('object_id',inspection_slots[i]+1) if i in inspection_slots else None})
    values=np.asarray(states)
    velocity=_tangents(times,values)
    return {'version':'flight-v1','seed':seed,'profile':profile,'duration_s':duration,
            'state_axes':['center_x_px','center_y_px','log_crop_width_px','yaw_rad','pitch_rad','roll_rad'],
            'times_s':times.tolist(),'states':values.tolist(),'velocities':velocity.tolist(),'segments':events,
            'warnings':['Не все дефекты получили отдельный проход: увеличьте длительность или уменьшите число объектов.'] if len(visits)<len(objects) else []}


def sample_flight(plan,size,count,fps):
    times=np.asarray(plan['times_s']);values=np.asarray(plan['states']);velocity=np.asarray(plan['velocities'])
    iw,ih=size
    phase=(plan['seed']%10000)*.071
    jitter=.00015 if plan['profile']=='calm' else .0007
    samples=[]
    for i in range(count):
        t=i/fps
        state,index=interpolate(times,values,velocity,t)
        cw=float(math.exp(state[2]));ch=cw*9/16
        # Apply bounds after interpolation too. No image padding or repeated edge pixels.
        x=float(np.clip(state[0]-cw/2,0,max(0,iw-cw)))
        y=float(np.clip(state[1]-ch/2,0,max(0,ih-ch)))
        amplitude=0. if plan.get('version')=='focus-flight-v1' else jitter
        yaw=float(state[3]+amplitude*math.sin(8.3*t+phase))
        pitch=float(state[4]+amplitude*.65*math.sin(10.1*t+phase*.7))
        roll=float(state[5]+amplitude*.5*math.sin(12.7*t+phase*.3))
        if plan.get('version')=='focus-flight-v1' and plan['segments'][index]['maneuver']=='target_transition':
            u=(t-times[index])/(times[index+1]-times[index])
            envelope=math.sin(math.pi*np.clip(u,0,1))**4
            yaw+=.025*math.sin(phase+index)*envelope
            pitch+=.015*math.cos(phase*.7+index)*envelope
            roll+=.002*math.sin(phase*.3+index)*envelope
        samples.append({'crop_xywh':(x,y,cw,ch),'attitude_rad':(yaw,pitch,roll),
                        'segment_index':index,'maneuver':plan['segments'][index]['maneuver']})
    return samples


def make_focus_flight(size,objects,focus_points,duration,seed,profile='calm',overview=False):
    """Visit EVERY explicit target, with a real dwell and no random zoom into empty space."""
    iw,ih=size;base=min(iw,ih*16/9);rng=np.random.default_rng(seed)
    targets=[{'kind':'defect','target_id':o.get('object_id',i+1),**o} for i,o in enumerate(objects)]
    targets += [{'kind':'context','target_id':p.get('point_id',i+1),**p} for i,p in enumerate(focus_points)]
    if overview:
        targets.append({'kind':'overview','target_id':1,'label':'Общий план',
                        'bbox':[(iw-base)/2,(ih-base*9/16)/2,(iw+base)/2,(ih+base*9/16)/2]})
    order=rng.permutation(len(targets)).tolist()
    # With enough context points, start/end on context instead of locking onto the defect.
    if len(focus_points)>=2:
        context=[i for i in order if targets[i]['kind']=='context']
        order=[context[0]]+[i for i in order if i not in (context[0],context[-1])]+[context[-1]]
    frames=[];warnings=[]
    for i in order:
        target=targets[i];x1,y1,x2,y2=target['bbox']
        required=max(x2-x1,(y2-y1)*16/9)
        width=min(base,max(required*1.35,base*.12))
        cx=float(np.clip((x1+x2)/2,width/2,iw-width/2))
        cy=float(np.clip((y1+y2)/2,width*9/32,ih-width*9/32))
        frames.append(np.array([cx,cy,math.log(width),0.,0.,0.]))
        if target['kind']=='context':
            crop=(cx-width/2,cy-width*9/32,cx+width/2,cy+width*9/32)
            if any(min(crop[2],o['bbox'][2])>max(crop[0],o['bbox'][0]) and min(crop[3],o['bbox'][3])>max(crop[1],o['bbox'][1]) for o in objects):
                warnings.append(f'В точке «{target["label"]}» дефект может оставаться видимым: рамки расположены близко или перекрываются.')
    n=len(frames)
    hold=2.
    travel_budget=duration-n*hold
    weights=rng.uniform(.8,1.2,n-1)
    distances=np.array([np.linalg.norm((b[:2]-a[:2])/[iw,ih]) for a,b in zip(frames,frames[1:])])
    weights*=.5+distances
    transitions=2.+(travel_budget-2*(n-1))*weights/weights.sum()
    states=[frames[0]];times=[0.];segments=[]
    def append(state,seconds,kind,target):
        start=times[-1];times.append(start+float(seconds));states.append(state)
        segments.append({'start_s':start,'end_s':times[-1],'maneuver':kind,
                         'target_kind':target['kind'],'target_id':target['target_id'],
                         'label':target['label']})
    for j,index in enumerate(order):
        if j:append(frames[j],transitions[j-1],'target_transition',targets[index])
        append(frames[j],hold,'focus_hold',targets[index])
    return {'version':'focus-flight-v1','seed':seed,'profile':profile,'duration_s':duration,
            'times_s':times,'states':np.asarray(states).tolist(),
            'velocities':np.zeros_like(states).tolist(),'segments':segments,
            'targets':[targets[i] for i in order],'warnings':warnings,
            'hold_seconds':hold,'state_axes':['center_x_px','center_y_px','log_crop_width_px','yaw_rad','pitch_rad','roll_rad']}
