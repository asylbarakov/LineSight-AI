import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from generator import generate,validate
from effects import CaptureEffects
from flight import make_focus_flight,sample_flight


class CaptureOptionsTests(unittest.TestCase):
    objects=[{'label':'defect','bbox':[700,250,800,350]}]

    def test_duration_and_overview_limits(self):
        for duration in (120,180):
            c=validate({'duration':duration,'objects':self.objects,'overview':True},(1280,720))
            p=make_focus_flight((1280,720),c['objects'],[],duration,42,overview=True)
            self.assertAlmostEqual(p['times_s'][-1],duration)
            samples=sample_flight(p,(1280,720),duration*15,15)
            self.assertTrue(any(s['crop_xywh'][2]>=1279 for s in samples))
        for extra in ({'duration':181},{'noise_strength':float('nan')},{'blur_strength':1.1}):
            with self.assertRaises(ValueError):validate({'objects':self.objects,**extra},(1280,720))
        with self.assertRaisesRegex(ValueError,'16:9'):
            validate({'objects':self.objects,'overview':True},(1280,1280))
        validate({'objects':self.objects,'focus_points':[{'bbox':[0,0,1280,720]}]},(1280,720))

    def test_effects_reproducible_intermittent_and_disabled(self):
        c=validate({'objects':self.objects,'width':640,'fps':15,'blur_strength':1,'noise_strength':1},(1280,720))
        frame=np.full((360,640,3),120,dtype=np.uint8)
        a,b=CaptureEffects(c),CaptureEffects(c)
        strengths=[]
        for i in range(90):
            crop=(i*5,0,900,506.25)
            left,info=a.apply(frame,i,crop);right,other=b.apply(frame,i,crop)
            np.testing.assert_array_equal(left,right);self.assertEqual(info,other)
            strengths.append(info['noise_sigma_255'])
        self.assertGreater(max(strengths),1)
        self.assertGreater(sum(v==0 for v in strengths),10)
        off=CaptureEffects({**c,'blur_strength':0,'noise_strength':0})
        for i in range(10):np.testing.assert_array_equal(off.apply(frame,i,(i*10,0,900,506.25))[0],frame)

    def test_export_overview_and_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);Image.new('RGB',(1280,720),'gray').save(p/'photo.png')
            result=generate(p/'photo.png',{'objects':self.objects,'overview':True,'duration':8,'width':640,'fps':15,'motion':'calm','blur_strength':.7,'noise_strength':.5},p/'out')
            visits=result['focus_visits']
            self.assertEqual({v['target_kind'] for v in visits},{'defect','overview'})
            rows=[json.loads(s) for s in (p/'out/tracks.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),120)
            self.assertTrue(all(len(r['objects'])==1 for r in rows))
            self.assertTrue(any(r['capture_effects']['blur_radius_px']>0 for r in rows))
