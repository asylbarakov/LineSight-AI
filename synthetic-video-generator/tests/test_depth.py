import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image,ImageDraw
from depth_estimation import protect_defects,stabilize_layers
from parallax import DepthRenderer,mask_bbox
from generator import generate


def scene():
    image=Image.new('RGB',(400,225),(20,40,80))
    draw=ImageDraw.Draw(image)
    draw.rectangle((130,80,159,129),fill=(255,255,0))
    draw.rectangle((170,70,209,139),fill=(255,0,0))
    near=np.full((225,400),.05,dtype='f4')
    near[80:130,130:160]=.4
    near[70:140,170:210]=.95
    objects=[{'object_id':1,'label':'back','bbox':[130,80,160,130]},
             {'object_id':2,'label':'front','bbox':[170,70,210,140]}]
    protected=np.zeros_like(near,dtype='uint8')
    protected[80:130,130:160]=1;protected[70:140,170:210]=1
    return image,near,protected,objects


class DepthTests(unittest.TestCase):
    def test_overview_with_capture_effects(self):
        image,near,protected,objects=scene()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);image.save(root/'source.png')
            with patch('depth_estimation.estimate_depth',return_value=(near,{'model_id':'fixture','revision':'test'})):
                result=generate(root/'source.png',{'motion':'depth','duration':8,'fps':15,'width':640,
                    'objects':[objects[1]],'overview':True,'blur_strength':.5,'noise_strength':.5},root/'result')
            self.assertEqual({v['target_kind'] for v in result['focus_visits']},{'defect','overview'})
            rows=[json.loads(line) for line in (root/'result/tracks.jsonl').read_text().splitlines()]
            self.assertTrue(any(row['capture_effects']['noise_sigma_255']>0 for row in rows))

    def test_focus_hold_in_depth_mode(self):
        image,near,protected,objects=scene()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);image.save(root/'source.png')
            with patch('depth_estimation.estimate_depth',return_value=(near,{'model_id':'fixture','revision':'test'})):
                result=generate(root/'source.png',{'motion':'depth','duration':8,'fps':15,'width':640,
                    'objects':[objects[1]],'focus_points':[{'label':'other','bbox':[30,30,70,70]}]},root/'result')
            self.assertEqual(len(result['focus_visits']),2)
            self.assertTrue(all(v['visible_fraction']>=.98 for v in result['focus_visits']))
            self.assertEqual(len(result['objects']),1)

    def test_overlapping_protection_is_flat_and_does_not_change_rgb(self):
        near=np.random.default_rng(42).random((120,200)).astype('f4')
        boxes=[{'bbox':[50,30,100,70]},{'bbox':[80,50,140,90]}]
        effective,protected=protect_defects(near,boxes,(200,120))
        self.assertAlmostEqual(float(np.std(effective[protected>0])),0,places=6)
        stable=stabilize_layers(effective)
        self.assertEqual(len(np.unique(stable[protected>0])),1)
        np.testing.assert_equal(near[0,0],effective[0,0])

    def test_parallax_occlusion_and_bbox_follow_actual_original_pixels(self):
        image,near,protected,objects=scene()
        renderer=DepthRenderer(image,near,protected,objects,(320,180))
        try:
            pose={'eye':[0,0,0],'rotation':np.eye(3).tolist(),'intrinsics':[480,480,160,90]}
            first,items=renderer.render(pose)
            self.assertEqual(renderer.last_reconstructed_fraction,0)
            # At the original viewpoint, depth layers must reconstruct the photo exactly.
            source=np.asarray(image,dtype=float)
            expected=(source[22:202,40:360]+source[23:203,40:360])/2
            self.assertLess(float(np.abs(first.astype(float)-expected).mean()),1.)
            centers=[(o['bbox_xyxy_px'][0]+o['bbox_xyxy_px'][2])/2 for o in items]
            pose['eye']=[.1,0,0]
            shifted,new=renderer.render(pose)
            front_shift=(new[1]['bbox_xyxy_px'][0]+new[1]['bbox_xyxy_px'][2])/2-centers[1]
            # Closer geometry moves farther in screen space, and occludes the rear object.
            self.assertLess(front_shift,-40)
            self.assertGreater(new[0]['occluded_fraction'],.1)
            self.assertFalse(new[0]['keyframe_eligible'])
            _,uv=renderer.draw(pose)
            mask=(uv[:,:,3]>.5)&(uv[:,:,3]<1.5)&(uv[:,:,0]>=170/400)&(uv[:,:,0]<210/400)&(uv[:,:,1]>=70/225)&(uv[:,:,1]<140/225)
            self.assertEqual(mask_bbox(mask),new[1]['bbox_xyxy_px'])
            self.assertGreater(np.mean(shifted[mask][:,0]),245)
            self.assertLess(np.mean(shifted[mask][:,1]),10)
            self.assertGreater(renderer.last_reconstructed_fraction,0)
        finally:renderer.close()

    def test_depth_mp4_exports_maps_and_keyframe_provenance(self):
        image,near,protected,objects=scene()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';image.save(source)
            with patch('depth_estimation.estimate_depth',return_value=(near,{'model_id':'test-fixture','revision':'test'})):
                result=generate(source,{'motion':'depth','duration':1,'fps':15,'width':640,'objects':objects},root/'result')
            self.assertEqual(result['video']['frame_count'],15)
            self.assertIsNotNone(result['objects'][0]['keyframe'])
            key=result['objects'][0]['keyframe']
            self.assertTrue((root/'result'/key['original_pixels_mask']).exists())
            tracks=[json.loads(line) for line in (root/'result/tracks.jsonl').read_text().splitlines()]
            self.assertEqual(tracks[key['frame_index']]['objects'][0]['bbox'],key['bbox'])
            self.assertTrue((root/'result/depth_raw.npy').exists())
            self.assertEqual(len(tracks),15)


if __name__=='__main__':unittest.main()
