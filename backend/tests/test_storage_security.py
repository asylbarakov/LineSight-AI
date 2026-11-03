import io
import time
import uuid

import jwt
import pytest

from app import security, storage
from app.config import Settings


def make_settings(**over):
    env = {"ADMIN_LOGIN": "admin", "ADMIN_PASSWORD": "pw", "SECRET_KEY": "k" * 40, "TOKEN_TTL_HOURS": "12"}
    env.update(over)
    return Settings.from_env(env)


# ---------- хранилище ----------

def test_inspection_dir_creates_frames(tmp_path):
    iid = str(uuid.uuid4())
    d = storage.inspection_dir(str(tmp_path), iid)
    assert d == (tmp_path / "inspections" / iid).resolve()
    assert (d / "frames").is_dir()


@pytest.mark.parametrize("bad", ["../x", "abc", "..", "", "1234/../../etc"])
def test_inspection_id_must_be_uuid(tmp_path, bad):
    with pytest.raises(storage.UnsafePath):
        storage.inspection_dir(str(tmp_path), bad)


def test_safe_join_blocks_traversal(tmp_path):
    with pytest.raises(storage.UnsafePath):
        storage.safe_join(tmp_path, "..", "secret.txt")
    with pytest.raises(storage.UnsafePath):
        storage.safe_join(tmp_path, "/etc/passwd")


def test_relative_path_cannot_escape(tmp_path):
    iid = str(uuid.uuid4())
    storage.inspection_dir(str(tmp_path), iid)
    ok = storage.resolve_relative(str(tmp_path), iid, "frames/a.jpg")
    assert ok.name == "a.jpg"
    with pytest.raises(storage.UnsafePath):
        storage.resolve_relative(str(tmp_path), iid, "../../x")


def test_frame_name_validation(tmp_path):
    iid = str(uuid.uuid4())
    storage.inspection_dir(str(tmp_path), iid)
    assert storage.frame_file(str(tmp_path), iid, "tower_1.jpg").name == "tower_1.jpg"
    for bad in ["../x.jpg", "a/b.jpg", "x.png", ".jpg", "a b.jpg"]:
        with pytest.raises(storage.UnsafePath):
            storage.frame_file(str(tmp_path), iid, bad)


def test_save_stream_writes_in_chunks(tmp_path):
    dest = tmp_path / "v.mp4"
    data = b"x" * (2 * 1024 * 1024 + 5)
    assert storage.save_stream(io.BytesIO(data), dest, max_bytes=10 * 1024 * 1024) == len(data)
    assert dest.read_bytes() == data


def test_save_stream_rejects_too_large_and_removes_file(tmp_path):
    dest = tmp_path / "v.mp4"
    with pytest.raises(storage.FileTooLarge):
        storage.save_stream(io.BytesIO(b"x" * 5000), dest, max_bytes=1000)
    assert not dest.exists()


def test_delete_inspection_dir(tmp_path):
    iid = str(uuid.uuid4())
    d = storage.inspection_dir(str(tmp_path), iid)
    (d / "video.mp4").write_bytes(b"1")
    storage.delete_inspection_dir(str(tmp_path), iid)
    assert not d.exists()


# ---------- вход администратора ----------

def test_credentials():
    s = make_settings()
    assert security.check_credentials(s, "admin", "pw")
    assert not security.check_credentials(s, "admin", "wrong")
    assert not security.check_credentials(s, "root", "pw")
    assert not security.check_credentials(s, "", "")


def test_unicode_credentials_do_not_crash():
    s = make_settings(ADMIN_PASSWORD="пароль")
    assert security.check_credentials(s, "admin", "пароль")
    assert not security.check_credentials(s, "admin", "пароль1")


def test_token_roundtrip_and_ttl():
    s = make_settings()
    token, ttl = security.create_token(s)
    assert ttl == 12 * 3600
    assert security.verify_token(s, token)


def test_expired_token_is_rejected():
    s = make_settings()
    token, _ = security.create_token(s, now=time.time() - 13 * 3600)
    assert not security.verify_token(s, token)


def test_token_signed_with_other_key_is_rejected():
    s = make_settings()
    other = make_settings(SECRET_KEY="z" * 40)
    token, _ = security.create_token(other)
    assert not security.verify_token(s, token)


def test_garbage_and_wrong_subject_tokens_are_rejected():
    s = make_settings()
    assert not security.verify_token(s, "garbage")
    forged = jwt.encode({"sub": "someone", "exp": int(time.time()) + 100}, s.secret_key, algorithm="HS256")
    assert not security.verify_token(s, forged)


def test_missing_secret_generates_random_one():
    a = Settings.from_env({"ADMIN_PASSWORD": "x"})
    b = Settings.from_env({"ADMIN_PASSWORD": "x"})
    assert a.secret_key and a.secret_key != b.secret_key


def test_limits_from_env():
    s = make_settings(MAX_UPLOAD_MB="5")
    assert s.max_upload_bytes == 5 * 1024 * 1024
