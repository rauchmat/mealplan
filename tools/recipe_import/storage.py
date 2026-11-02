"""Validate before atomic replacement; refuse concurrent catalog edits."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


@contextmanager
def locked(path):
    # O_EXCL works without platform-specific locking libraries; never break a stale
    # lock automatically. A killed process requires checking/removing it manually.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def atomic_json(path, value, expected=None, validator=None):
    path = Path(path)
    if validator:
        validator(value)
    serialized = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        current = path.read_bytes() if path.exists() else None
        if current != expected:
            raise ValueError("concurrent_file_change")
        fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            # Recheck after writing the temp file, before replacing the destination.
            if (path.read_bytes() if path.exists() else None) != expected:
                raise ValueError("concurrent_file_change")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
