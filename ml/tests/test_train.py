"""CPU-only baseline orchestration helpers; no neural model or CUDA dependency."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import train
import prepare_yolo


def test_batch_vram_policy():
    assert train.choose_batch(15*1024**3)==16
    assert train.choose_batch(8*1024**3)==8
    assert train.choose_batch(15*1024**3,8)==8
    with pytest.raises(ValueError): train.choose_batch(4*1024**3)


def test_matching_distinguishes_duplicates_misses_and_false_positives():
    gt=[[0,0,10,10],[20,20,30,30]]
    pred=[{'xyxy':[0,0,10,10],'confidence':.9},
          {'xyxy':[0,0,10,10],'confidence':.7},
          {'xyxy':[50,50,60,60],'confidence':.5}]
    result=train.match_boxes(gt,pred,.5)
    assert result=={'tp':[{'prediction':0,'ground_truth':0}],'fp':[1,2],'fn':[1]}
    assert train.match_boxes(gt,[],.5)['fn']==[0,1]


def test_checkpoint_backup_copies_only_at_interval(tmp_path):
    run=tmp_path/'run'; (run/'training/weights').mkdir(parents=True)
    (run/'training/weights/last.pt').write_bytes(b'unit-test checkpoint, not model weights')
    (run/'training/results.csv').write_text('epoch\n1\n')
    backup=tmp_path/'drive'
    callback=train.checkpoint_callback(run,backup,5)
    callback(SimpleNamespace(epoch=0,epochs=25))
    assert (backup/'training/weights/last.pt').exists()
    (run/'training/results.csv').write_text('epoch\n1\n2\n')
    callback(SimpleNamespace(epoch=1,epochs=25))
    assert (backup/'training/results.csv').read_text()=='epoch\n1\n'
    callback(SimpleNamespace(epoch=4,epochs=25))
    assert (backup/'training/results.csv').read_text()=='epoch\n1\n2\n'
    assert not list(backup.rglob('*.partial'))
    with pytest.raises(ValueError): train.sync_artifacts(run,run/'backup')


def test_export_contains_recovery_artifacts_without_dataset(tmp_path):
    run=tmp_path/'run'; run.mkdir()
    (run/'errors.txt').write_text('unit-test exception')
    (run/'manifest.json').write_text('{}')
    (run/'data_view').mkdir(); (run/'data_view/source.jpg').write_bytes(b'not for export')
    target=train.export_results(run)
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist())=={'errors.txt','manifest.json'}


def test_training_view_copies_labels_and_never_stages_test(tmp_path):
    source=tmp_path/'dataset'
    for split in ('train','val','test'):
        for kind in ('images','labels'): (source/kind/split).mkdir(parents=True)
        (source/'images'/split/'a.jpg').write_bytes(b'unit test image bytes')
        (source/'labels'/split/'a.txt').write_text('0 .5 .5 .2 .2\n')
    view=train.stage_training_view(source,tmp_path/'view')
    assert not (view/'images/test').exists()
    (view/'labels/train/a.txt').write_text('edited derived labels')
    assert (source/'labels/train/a.txt').read_text()=='0 .5 .5 .2 .2\n'


def test_preflight_is_cpu_safe_and_uses_existing_yaml(tmp_path,monkeypatch):
    pytest.importorskip('yaml')
    data=tmp_path/'data.yaml'
    data.write_text('path: '+json.dumps(tmp_path.as_posix())+'\ntrain: images/train\nval: images/val\nnames:\n  0: czjyz_ps\n')
    (tmp_path/'manifest.json').write_text(json.dumps({'split_counts':{'train':3,'val':1,'test':1}}))
    monkeypatch.setattr(train,'validate_dataset',lambda path:{'status':'passed'})
    config={'model':'yolo11n.pt','imgsz':640,'epochs':25}
    assert train.preflight(data,config)['model_evaluation_split']=='val'
    config['epochs']=100
    with pytest.raises(ValueError): train.preflight(data,config)


def test_training_bundle_keeps_frozen_plan_and_pins_dependencies(tmp_path):
    plan=tmp_path/'plan.json'; plan.write_text(json.dumps({'provenance':{'git_head':'fixture'}}))
    target=tmp_path/'bundle.zip'
    prepare_yolo.create_bundle(plan,target,training=True)
    with zipfile.ZipFile(target) as z:
        assert {'train.py','requirements-colab.txt','baseline_czjyz_ps_v1.json','plan.json'} <= set(z.namelist())
        assert z.read('plan.json')==plan.read_bytes()
        metadata=json.loads(z.read('bundle_manifest.json'))
        assert metadata['purpose']=='manual_training'
        assert metadata['git_sha']=='fixture'
        assert b'ultralytics==8.3.228' in z.read('requirements-colab.txt')
