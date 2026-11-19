import unittest
import numpy as np
from camera import drone_matrix,points
from flight import make_flight,sample_flight,interpolate


class FlightTests(unittest.TestCase):
    def setUp(self):
        self.size=(1368,769)
        self.objects=[{'object_id':1,'bbox':[858,378,970,466]}]

    def test_seed_changes_route_and_reproduces_exactly(self):
        a=make_flight(self.size,self.objects,30,42)
        self.assertEqual(a,make_flight(self.size,self.objects,30,42))
        b=make_flight(self.size,self.objects,30,43)
        self.assertNotEqual(a['states'],b['states'])
        self.assertNotEqual(a['times_s'],b['times_s'])
        self.assertGreater(len({s['maneuver'] for s in a['segments']}),2)
        self.assertIn('inspection_pass',[s['maneuver'] for s in a['segments']])
        self.assertGreater(np.max(np.linalg.norm(np.array(a['velocities'])[1:-1,:2],axis=1)),1)

    def test_same_physical_motion_at_different_fps(self):
        plan=make_flight(self.size,self.objects,30,7)
        a=sample_flight(plan,self.size,450,15)
        b=sample_flight(plan,self.size,900,30)
        self.assertEqual(a,b[::2])

    def test_positions_velocity_and_acceleration_continuous_at_knots(self):
        plan=make_flight(self.size,self.objects,30,42)
        times=np.array(plan['times_s']);values=np.array(plan['states']);v=np.array(plan['velocities'])
        for t in times[1:-1]:
            eps=1e-3
            f=lambda at:interpolate(times,values,v,at)[0]
            center=f(t)
            np.testing.assert_allclose(f(t-eps),center,atol=.1)
            left=(center-f(t-eps))/eps;right=(f(t+eps)-center)/eps
            np.testing.assert_allclose(left,right,atol=.001)
            acc_left=(center-2*f(t-eps)+f(t-2*eps))/eps**2
            acc_right=(f(t+2*eps)-2*f(t+eps)+center)/eps**2
            np.testing.assert_allclose(acc_left,acc_right,atol=.15)

    def test_all_freedoms_and_no_unknown_source_corners(self):
        for size in [self.size,(600,1800)]:
            objects=[{'bbox':[20,20,120,120]}]
            all_motion=[]
            for seed in (1,42,81):
                p=make_flight(size,objects,30,seed)
                samples=sample_flight(p,size,450,15)
                all_motion.extend([s['attitude_rad'] for s in samples])
                for i,s in enumerate(samples[::9]):
                    _,inverse=drone_matrix(s['crop_xywh'],size,(640,360),i*9/15,seed,attitude=s['attitude_rad'])
                    corners=points(inverse,[(0,0),(640,0),(640,360),(0,360)])
                    self.assertTrue((corners>=-1e-6).all())
                    self.assertTrue((corners<=np.array(size)+1e-6).all())
            variation=np.ptp(np.array(all_motion),axis=0)
            self.assertGreater(variation[0],.05)
            self.assertGreater(variation[1],.04)


if __name__=='__main__':unittest.main()
