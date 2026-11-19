import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from flight import make_focus_flight,sample_flight
from generator import validate,generate
from camera import drone_matrix,project


class FocusTests(unittest.TestCase):
    size=(1600,900)
    defects=[{'object_id':1,'label':'defect','bbox':[1100,400,1200,500]}]
    context=[{'point_id':1,'label':'left','bbox':[100,100,230,230]},
             {'point_id':2,'label':'bottom','bbox':[450,700,600,800]}]

    def test_all_targets_hold_and_context_excludes_distant_defect(self):
        for seed in (7,42,81):
            plan=make_focus_flight(self.size,self.defects,self.context,30,seed)
            samples=sample_flight(plan,self.size,750,25)
            holds=[s for s in plan['segments'] if s['maneuver']=='focus_hold']
            self.assertEqual(len(holds),3)
            self.assertEqual({(s['target_kind'],s['target_id']) for s in holds},{('defect',1),('context',1),('context',2)})
            for hold in holds:
                self.assertAlmostEqual(hold['end_s']-hold['start_s'],2)
                i=round((hold['start_s']+hold['end_s'])/2*25);s=samples[i]
                target=next(t for t in plan['targets'] if t['kind']==hold['target_kind'] and t['target_id']==hold['target_id'])
                matrix,_=drone_matrix(s['crop_xywh'],self.size,(640,360),i/25,seed,attitude=s['attitude_rad'])
                self.assertGreater(project(target['bbox'],matrix,(640,360))['visible_fraction'],.99)
                if target['kind']=='context':self.assertFalse(project(self.defects[0]['bbox'],matrix,(640,360))['visible'])
            self.assertEqual(plan,make_focus_flight(self.size,self.defects,self.context,30,seed))

    def test_validation_requires_enough_time_and_valid_context(self):
        config={'objects':self.defects,'focus_points':self.context,'duration':5}
        with self.assertRaisesRegex(ValueError,'минимум 12'):validate(config,self.size)
        config['duration']=30
        self.assertEqual(len(validate(config,self.size)['objects']),1)
        config['focus_points']=[{'bbox':[0,0,1700,20]}]
        with self.assertRaises(ValueError):validate(config,self.size)

    def test_context_does_not_become_defect_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);Image.new('RGB',self.size,'#456789').save(root/'image.png')
            result=generate(root/'image.png',{'objects':self.defects,'focus_points':self.context,'duration':12,'fps':15,'width':640,'motion':'calm'},root/'result')
            self.assertEqual(len(result['objects']),1)
            self.assertEqual(len(result['focus_visits']),3)
            self.assertEqual(len(result['focus_points']),2)
            tracks=[json.loads(line) for line in (root/'result/tracks.jsonl').read_text().splitlines()]
            self.assertTrue(all(len(t['objects'])==1 and t['objects'][0]['label']=='defect' for t in tracks))


if __name__=='__main__':unittest.main()
