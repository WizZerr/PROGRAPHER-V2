"""SP-AUTO-01 safe retry setup tests: only synthetic private catalogs."""
from __future__ import annotations

import hashlib

import pytest

from app.lightroom_bridge import sp_auto01_retry_setup as setup


def _setup_source(tmp_path):
    root = tmp_path / setup.ROOT_NAME
    base = root / setup.PARENT
    origin = base / setup.SOURCE
    origin.mkdir(parents=True)
    catalog = origin / (setup.SOURCE + ".lrcat")
    catalog.write_bytes(b"fake-private-disposable-catalog\0" * 1200)
    previews = origin / (setup.SOURCE + " Smart Previews.lrdata")
    previews.mkdir()
    (previews / "preview").mkdir()
    (previews / "preview" / "block.dat").write_bytes(b"fake-smart-preview" * 128)
    data = origin / (setup.SOURCE + ".lrcat-data")
    data.mkdir()
    (data / "mask.dat").write_bytes(b"fake catalog metadata" * 10)
    failed = origin / "SP_01_AUTO_BRIDGE"
    failed.mkdir()
    (failed / "result.txt").write_text("status=error\nstage=develop_reset\n")
    return root, origin, catalog


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_copy_clones_catalog_previews_metadata_but_no_failure_job(tmp_path):
    root, origin, source = _setup_source(tmp_path)
    original_sha = _sha(source)
    output = setup.clone(private_root=root)
    assert output == root / setup.PARENT / setup.DEST / (setup.DEST + ".lrcat")
    assert _sha(output) == original_sha
    clone_folder = output.parent
    assert (clone_folder / (setup.DEST + " Smart Previews.lrdata") / "preview" / "block.dat").is_file()
    assert (clone_folder / (setup.DEST + ".lrcat-data") / "mask.dat").is_file()
    assert not (clone_folder / "SP_01_AUTO_BRIDGE").exists()
    assert _sha(source) == original_sha
    assert (origin / "SP_01_AUTO_BRIDGE" / "result.txt").read_text().startswith("status=error")


def test_repeat_setup_does_not_overwrite_existing_catalog(tmp_path):
    root, _, source = _setup_source(tmp_path)
    setup.clone(private_root=root)
    before = _sha(source)
    with pytest.raises(FileExistsError):
        setup.clone(private_root=root)
    assert _sha(source) == before


@pytest.mark.parametrize("active_suffix", [".lrcat.lock", ".lrcat-wal", ".lrcat-shm"])
def test_refuse_copy_from_active_catalog(tmp_path, active_suffix):
    root, origin, source = _setup_source(tmp_path)
    (origin / (setup.SOURCE + active_suffix)).write_text("active")
    with pytest.raises(RuntimeError):
        setup.clone(private_root=root)
    assert not (root / setup.PARENT / setup.DEST).exists()


def test_reject_unexpected_redirects_in_preview_store(tmp_path):
    root, origin, source = _setup_source(tmp_path)
    preview = origin / (setup.SOURCE + " Smart Previews.lrdata")
    redirect = preview / "link"
    try:
        redirect.symlink_to(root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Windows symlinks not available")
    with pytest.raises(ValueError, match="symlink"):
        setup.clone(private_root=root)
    assert not (root / setup.PARENT / setup.DEST).exists()


def test_missing_smart_preview_store_rejected(tmp_path):
    root, origin, _ = _setup_source(tmp_path)
    import shutil
    shutil.rmtree(origin / (setup.SOURCE + " Smart Previews.lrdata"))
    with pytest.raises(ValueError, match="Smart Preview"):
        setup.clone(private_root=root)
    assert not (root / setup.PARENT / setup.DEST).exists()
