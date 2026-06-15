from __future__ import annotations

import gzip
import hashlib

from helpers import make_bmp

from kitchen_display_server.storage import Storage, compute_etag


def test_compute_etag_format_matches_contract():
    data = b"hello"
    etag = compute_etag(data)
    expected = '"' + hashlib.sha256(data).hexdigest()[:16] + '"'
    assert etag == expected
    assert len(etag) == 18  # quote + 16 hex + quote


def test_compute_etag_deterministic():
    data = b"deterministic input"
    assert compute_etag(data) == compute_etag(data)


def test_compute_etag_changes_with_content():
    assert compute_etag(b"a") != compute_etag(b"b")


def test_write_image_creates_files_and_returns_meta(tmp_path):
    storage = Storage(state_dir=tmp_path)
    bmp = make_bmp()
    meta = storage.write_image(bmp)
    assert (tmp_path / "current.bmp.gz").exists()
    assert (tmp_path / "current.etag").exists()
    assert (tmp_path / "current.meta.json").exists()
    assert meta["etag"] == compute_etag(bmp)
    assert meta["sha256"] == hashlib.sha256(bmp).hexdigest()
    assert meta["bytes_raw"] == len(bmp)
    assert meta["bytes_gz"] == (tmp_path / "current.bmp.gz").stat().st_size


def test_read_image_gz_roundtrips(tmp_path):
    storage = Storage(state_dir=tmp_path)
    bmp = make_bmp()
    storage.write_image(bmp)
    gz = storage.read_image_gz()
    assert gzip.decompress(gz) == bmp


def test_read_etag_matches_compute(tmp_path):
    storage = Storage(state_dir=tmp_path)
    bmp = make_bmp()
    meta = storage.write_image(bmp)
    assert storage.read_etag() == meta["etag"]


def test_has_image_lifecycle(tmp_path):
    storage = Storage(state_dir=tmp_path)
    assert storage.has_image() is False
    storage.write_image(make_bmp())
    assert storage.has_image() is True
    storage.clear_image()
    assert storage.has_image() is False
    assert not (tmp_path / "current.bmp.gz").exists()
    assert not (tmp_path / "current.etag").exists()
    assert not (tmp_path / "current.meta.json").exists()


def test_record_device_query_bounded_ring(tmp_path):
    storage = Storage(state_dir=tmp_path)
    for i in range(150):
        storage.record_device_query({"i": i, "status": 200})
    state = storage.read_device_state()
    assert len(state["recent"]) == 100
    # Newest first
    assert state["recent"][0]["i"] == 149
    assert state["recent"][-1]["i"] == 50
    assert state["last_seen_at"] == state["recent"][0]["at"]


def test_record_device_query_persists_battery(tmp_path):
    storage = Storage(state_dir=tmp_path)
    storage.record_device_query({"status": 200, "battery_pct": 87, "ua": "ESP"})
    state = storage.read_device_state()
    assert state["recent"][0]["battery_pct"] == 87
    assert state["last_battery_pct"] == 87
    assert state["last_user_agent"] == "ESP"


def test_read_device_state_empty_when_no_queries(tmp_path):
    storage = Storage(state_dir=tmp_path)
    state = storage.read_device_state()
    assert state == {
        "last_seen_at": None,
        "last_battery_pct": None,
        "last_user_agent": None,
        "recent": [],
    }


def test_atomic_write_no_tear_on_interrupted_meta(tmp_path):
    """Stray .tmp files left by an interrupted prior write are removed on the next
    successful write."""
    storage = Storage(state_dir=tmp_path)
    storage.write_image(make_bmp())
    first_etag = storage.read_etag()
    # Simulate a partial write: drop a stray tmp file that should be ignored.
    (tmp_path / "current.bmp.gz.tmp").write_bytes(b"garbage")
    storage.write_image(make_bmp(mode="L"))  # different content → different etag
    assert storage.read_etag() != first_etag
    assert not (tmp_path / "current.bmp.gz.tmp").exists()
