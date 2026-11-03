from ml.tracking import IoUTracker, RawDetection, iou, similarity


def test_iou_basic():
    assert iou((0, 0, 1, 1), (0, 0, 1, 1)) == 1.0
    assert iou((0, 0, 0.1, 0.1), (0.5, 0.5, 0.1, 0.1)) == 0.0
    assert 0 < iou((0, 0, 0.2, 0.2), (0.1, 0, 0.2, 0.2)) < 1


def test_one_moving_object_gives_one_track():
    tr = IoUTracker()
    ids = set()
    for i in range(10):
        x = 0.1 + 0.01 * i  # медленный сдвиг камеры
        out = tr.update([RawDetection("tower", 0.9, (x, 0.2, 0.05, 0.5))])
        ids.add(out[0].track_id)
    assert len(ids) == 1


def test_two_objects_keep_separate_ids():
    tr = IoUTracker()
    last = None
    for i in range(6):
        out = tr.update(
            [
                RawDetection("insulator", 0.9, (0.2 + 0.01 * i, 0.3, 0.03, 0.08)),
                RawDetection("insulator", 0.9, (0.6 + 0.01 * i, 0.3, 0.03, 0.08)),
            ]
        )
        ids = [d.track_id for d in out]
        assert len(set(ids)) == 2
        if last:
            assert ids == last
        last = ids


def test_different_classes_are_not_merged():
    tr = IoUTracker()
    tr.update([RawDetection("tower", 0.9, (0.1, 0.1, 0.2, 0.2))])
    out = tr.update([RawDetection("insulator", 0.9, (0.1, 0.1, 0.2, 0.2))])
    assert out[0].track_id == 2


def test_track_survives_short_gap_but_not_long_one():
    tr = IoUTracker(max_missed=2)
    first = tr.update([RawDetection("tower", 0.9, (0.1, 0.1, 0.1, 0.4))])[0].track_id
    tr.update([])
    assert tr.update([RawDetection("tower", 0.9, (0.1, 0.1, 0.1, 0.4))])[0].track_id == first
    for _ in range(4):
        tr.update([])
    assert tr.update([RawDetection("tower", 0.9, (0.1, 0.1, 0.1, 0.4))])[0].track_id != first


def test_box_cropped_by_frame_edge_keeps_track():
    # рамка сужается у края кадра: IoU мал, но она почти целиком лежит в прежней
    full = (0.8, 0.2, 0.2, 0.3)
    cropped = (0.9, 0.2, 0.1, 0.3)
    assert iou(full, cropped) < 0.55  # по одному IoU трек бы потерялся
    tr = IoUTracker(iou_min=0.55)
    a = tr.update([RawDetection("tower", 0.9, full)])[0].track_id
    b = tr.update([RawDetection("tower", 0.9, cropped)])[0].track_id
    assert a == b
    assert similarity(full, cropped) >= 0.55
