"""Small CPU checks for the one-class export and group-level splits."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import prepare_yolo as yolo


def test_letterbox_changes_size_not_semantics():
    obj={"width_px":100,"height_px":40,"actual_size":[1000,500]}
    assert yolo.letterbox_box(obj,640)==(64,25.6)
    assert yolo.letterbox_box(obj,960)==(96,38.4)
    assert yolo.letterbox_box(obj,1600,False)==(100,40)


def test_near_pair_filter_and_transitive_groups():
    features={"a":{"phash":0,"dhash":0,"size":[100,100]},
              "b":{"phash":3,"dhash":7,"size":[100,100]},
              "c":{"phash":3,"dhash":7,"size":[200,100]}}
    assert yolo.near_pairs(features)==[{"a":"a","b":"b","phash_distance":2,"dhash_distance":3}]
    groups=yolo.Groups(features)
    groups.union("a","b"); groups.union("b","c")
    assert len({groups.find(k) for k in features})==1


def fixture_plan(tmp_path):
    source=tmp_path/"source"; source.mkdir()
    rows=[]
    for i,split in enumerate(("train","val","test")):
        image=source/f"{i}.jpg"; image.write_bytes(f"fixture-{i}".encode())
        rows.append({"image":image.name,"group":str(i),"sha256":yolo.digest(image),"split":split,
                     "labels":[[0,.5,.5,.2,.4]]})
    return source,{"included":rows,"split_counts":{"train":1,"val":1,"test":1},"split_objects":{"train":1,"val":1,"test":1}}


def test_export_validation_rejects_overwrite_and_label_tampering(tmp_path):
    source,plan=fixture_plan(tmp_path)
    out=tmp_path/"dataset"
    yolo.export_plan(plan,source,out)
    assert yolo.validate_dataset(out)["status"]=="passed"
    with pytest.raises(FileExistsError): yolo.export_plan(plan,source,out)
    label=next((out/"labels/train").iterdir()); label.write_text("1 .5 .5 .2 .4\n")
    with pytest.raises(ValueError): yolo.validate_dataset(out)


def test_cross_split_group_and_source_path_escape_are_rejected(tmp_path):
    source,plan=fixture_plan(tmp_path)
    plan['included'][1]['group']=plan['included'][0]['group']
    with pytest.raises(ValueError,match="Cross-split"): yolo.export_plan(plan,source,tmp_path/'bad')
    plan['included'][1]['group']='unique'
    plan['included'][0]['image']='../outside.jpg'
    with pytest.raises(ValueError,match="Source/hash"): yolo.export_plan(plan,source,tmp_path/'escape')


def test_make_plan_requires_finished_semantic_review():
    with pytest.raises(ValueError,match="semantic review"):
        yolo.make_plan({}, {}, {}, [{"decision":"pending"}])


def test_no_target_is_not_a_negative_and_ambiguous_group_is_excluded():
    names=['a.jpg','b.jpg','empty.jpg']
    features={name:{'sha256':name} for name in names}
    objects=[{'image':name,'annotation':name+'.xml','class':'czjyz_ps',
              'width_px':20,'height_px':20,'short_side_px':20,'actual_size':[100,100],
              'image_xyxy':[10,10,30,30]} for name in names[:2]]
    report={'objects':objects,'invalid_annotations':[], 'duplicate_groups_with_different_projectable_labels':[],
            'exact_duplicate_image_groups':[], 'archive_provenance':{},'source_annotation_sha256':'fixture'}
    for key in ['missing_referenced_files','empty_annotations','images_without_xml','filename_reference_issues']:
        report[key]=[]
    groups={name:('ambiguous' if name=='b.jpg' else name) for name in names}
    review=[{'image':'b.jpg','decision':'uncertain'}]
    plan=yolo.make_plan(report,features,groups,review)
    assert [x['image'] for x in plan['included']]==['a.jpg']
    excluded={row['image']:row['reasons'] for row in plan['excluded']}
    assert 'no_verified_target_positive_not_a_negative' in excluded['empty.jpg']
    assert 'ambiguous_duplicate_or_semantic_review_group' in excluded['b.jpg']


def test_validation_rejects_nan_labels(tmp_path):
    source,plan=fixture_plan(tmp_path)
    output=tmp_path/'nan-dataset'
    yolo.export_plan(plan,source,output)
    next((output/'labels/train').iterdir()).write_text('0 nan .5 .2 .4\n')
    with pytest.raises(ValueError,match='labels differ'):
        yolo.validate_dataset(output)
