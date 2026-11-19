import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw
from generator import camera_path, generate, project_bbox, validate


class GeneratorTests(unittest.TestCase):
    def test_projection_and_clipping(self):
        obj = project_bbox([50, 20, 150, 120], (100, 0, 200, 200), (400, 400))
        self.assertEqual(obj['bbox_xyxy_px'], [0, 40, 100, 240])
        self.assertAlmostEqual(obj['visible_fraction'], .5)
        self.assertTrue(obj['truncated'])
        self.assertIsNone(project_bbox([0,0,10,10], (20,20,10,10), (100,100))['bbox'])

    def test_path_stays_inside_portrait_and_landscape(self):
        for size in [(4000,3000),(600,1800)]:
            objects=[{'bbox':[0,0,100,100]}]
            crops=list(camera_path(size,objects,150,42))
            self.assertEqual(crops,list(camera_path(size,objects,150,42)))
            for x,y,w,h in crops:
                self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                self.assertLessEqual(x+w,size[0]+1e-6);self.assertLessEqual(y+h,size[1]+1e-6)

    def test_validation(self):
        for box in [[0,0,200,50],[10,0,0,30],[0,0,float('nan'),30]]:
            with self.assertRaises(ValueError):
                validate({'objects':[{'label':'test','bbox':box}]},(100,100))

    def test_real_mp4_and_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source.png'
            image=Image.new('RGB',(1280,720),'#334455')
            ImageDraw.Draw(image).rectangle((700,250,800,350),fill='red');image.save(source)
            result=generate(source,{'duration':1,'fps':15,'width':640,
                'objects':[{'label':'defect','bbox':[700,250,800,350]}]},root/'result')
            self.assertEqual(result['video']['frame_count'],15)
            tracks=[json.loads(line) for line in (root/'result/tracks.jsonl').read_text().splitlines()]
            self.assertEqual(len(tracks),15)
            key=result['objects'][0]['keyframe']
            self.assertEqual(tracks[key['frame_index']]['objects'][0]['bbox'],key['bbox'])
            self.assertTrue((root/'result'/key['image']).is_file())
            self.assertTrue((root/'result/flight_plan.json').is_file())
            self.assertIsNotNone(tracks[0]['flight_motion'])
            with zipfile.ZipFile(root/'result/result.zip') as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn('video.mp4',archive.namelist())


if __name__ == '__main__':
    unittest.main()
