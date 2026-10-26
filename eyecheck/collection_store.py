"""Private, append-only numeric evidence and atomic manifests."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

SCHEMA = "eyecheck-numeric-session-v1"


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def dataset_root():
    root = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    if not root.is_absolute():
        raise ValueError("XDG_STATE_HOME must be an absolute path")
    return root / "eyecheck" / "datasets"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Dataset directory must be a real directory")
    if os.name == "posix" and (path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077):
        raise ValueError("Dataset directory must be owned by you with mode 0700")
    return path


def atomic_manifest(path, data):
    temp = path / (".manifest-" + uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(dumps(data) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path / "manifest.json")


class SessionStore:
    def __init__(self, path, metadata, resume_reserved=False):
        self.path = Path(path)
        if not resume_reserved:
            self.path.mkdir(mode=0o700, parents=False, exist_ok=False)
        private_directory(self.path)
        if resume_reserved:
            initial = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
            if initial.get("status") != "reserved" or initial.get("session_id") != self.path.name:
                raise ValueError("Worker requires its fresh reserved session")
            metadata = initial
        self.manifest = {**metadata, "schema": SCHEMA, "session_id": self.path.name,
                         "calibration_id": self.path.name + "-calibration-1",
                         "status": "running", "started_unix_ns": time.time_ns()}
        self.streams = {}
        try:
            for name in ("events", "observations"):
                fd = os.open(self.path / f"{name}.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                self.streams[name] = os.fdopen(fd, "w", encoding="utf-8", buffering=1)
            atomic_manifest(self.path, self.manifest)
        except BaseException:
            for stream in self.streams.values():
                stream.close()
            raise
        self.closed = False

    def append(self, name, row):
        self.streams[name].write(dumps({"schema": SCHEMA, "session_id": self.path.name,
                                       "calibration_id": self.manifest["calibration_id"], **row}) + "\n")

    def checkpoint(self, **details):
        self.manifest.update(details)
        atomic_manifest(self.path, self.manifest)

    def finish(self, status, **details):
        if self.closed:
            return
        self.closed = True
        for stream in self.streams.values():
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
        hashes = {f"{name}.jsonl": sha256_file(self.path / f"{name}.jsonl")
                  for name in self.streams}
        self.manifest.update(status=status, finished_unix_ns=time.time_ns(), file_sha256=hashes, **details)
        atomic_manifest(self.path, self.manifest)


def reserve(metadata):
    root = private_directory(dataset_root())
    path = root / (time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12])
    path.mkdir(mode=0o700, exist_ok=False)
    atomic_manifest(path, {**metadata, "schema": SCHEMA, "session_id": path.name, "status": "reserved"})
    return path


def mark_interrupted(path, reason):
    """Parent uses only after the child exits; preserve partial traces as evidence."""
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(status="incomplete", interruption=reason, finished_unix_ns=time.time_ns(),
                    recovery_note="Worker ended without normal finalization; JSONL may have a partial last line. Do not train from this session.")
    atomic_manifest(path, manifest)
