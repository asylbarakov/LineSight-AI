import unittest
import numpy as np
from PIL import Image, ImageDraw
from annotations import parse_voc
from camera import drone_matrix, points, project

XML = '''<annotation><size><width>5472</width><height>3078</height></size>
<object><name>nw</name><bndbox><xmin>1191</xmin><ymin>1394</ymin>
<xmax>2315</xmax><ymax>2129</ymax></bndbox></object></annotation>'''


class ImportTests(unittest.TestCase):
    def test_user_sample_and_multiple_objects(self):
        data=parse_voc(XML,5472,3078)
        self.assertEqual(data['objects'][0]['label'],'nw')
        self.assertEqual(data['objects'][0]['bbox'],[1191,1394,2315,2129])
        doubled=XML.replace('</annotation>',XML[XML.index('<object>'):XML.index('</object>')+9]+'</annotation>')
        self.assertEqual(len(parse_voc(doubled,5472,3078)['objects']),2)

    def test_bad_xml_size_and_coordinates(self):
        for text,w,h in [(XML,100,100), (XML.replace('1191','nan'),5472,3078),
                         (XML.replace('2315','100'),5472,3078),
                         ('<!DOCTYPE annotation>'+XML,5472,3078),('<annotation>',5472,3078)]:
            with self.assertRaises(Exception):parse_voc(text,w,h)


class CameraTests(unittest.TestCase):
    def test_rendered_marker_matches_projected_bbox(self):
        image=Image.new('RGB',(1000,700))
        ImageDraw.Draw(image).rectangle((350,250,449,349),fill=(255,0,0))
        forward,inverse=drone_matrix((100,100,800,450),(1000,700),(640,360),2,42)
        frame=image.transform((640,360),Image.Transform.PERSPECTIVE,tuple(inverse.flat)[:8],Image.Resampling.BILINEAR)
        ys,xs=np.where(np.asarray(frame)[:,:,0]>128)
        expected=project([350,250,450,350],forward,(640,360))['bbox_xyxy_px']
        np.testing.assert_allclose([xs.min(),ys.min(),xs.max()+1,ys.max()+1],expected,atol=2)

    def test_clipped_polygon_not_just_clipped_enclosing_box(self):
        item=project([50,20,150,120],np.array([[2,0,-200],[0,2,0],[0,0,1]]),(400,400))
        self.assertEqual(item['bbox_xyxy_px'],[0,40,100,240])
        self.assertAlmostEqual(item['visible_fraction'],.5)
        self.assertIsNone(project([0,0,5,5],np.array([[1,0,-10],[0,1,-10],[0,0,1]]),(100,100))['bbox'])

    def test_camera_roundtrip_and_no_black_borders(self):
        for size,crop in [((5472,3078),(0,0,5472,3078)),((600,1800),(0,0,600,337.5))]:
            for t in np.linspace(0,60,61):
                forward,inverse=drone_matrix(crop,size,(640,360),t,42)
                corners=points(inverse,[(0,0),(640,0),(640,360),(0,360)])
                self.assertTrue((corners>=0).all())
                self.assertTrue((corners<=size).all())
                np.testing.assert_allclose(points(forward,corners),[(0,0),(640,0),(640,360),(0,360)],atol=1e-8)
                self.assertGreater(abs(forward[2,0])+abs(forward[2,1]),0)
