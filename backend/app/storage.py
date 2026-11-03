import tempfile

from .config import get_settings


def storage_writable() -> bool:
    root = get_settings().storage_dir
    if not root.is_dir():
        return False
    try:
        with tempfile.TemporaryFile(dir=root):
            pass
        return True
    except OSError:
        return False
