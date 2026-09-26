"""Incremental ZIP_STORED batch assembly - items appended and their source
files deleted immediately, not just at the end (spec §5.3)."""

import os
import zipfile

from remote_web.zipper import BatchZipper


def _make_file(tmp_path, name, content=b"fake video bytes"):
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_add_and_delete_puts_the_item_in_the_archive(tmp_path):
    src = _make_file(tmp_path, "video1.mp4")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    z.add_and_delete(src, "video1.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["video1.mp4"]
        assert zf.read("video1.mp4") == b"fake video bytes"


def test_add_and_delete_removes_the_source_file_immediately(tmp_path):
    src = _make_file(tmp_path, "video1.mp4")
    z = BatchZipper(str(tmp_path / "batch.zip"))
    z.add_and_delete(src, "video1.mp4")
    assert not os.path.exists(src)
    z.close()


def test_archive_uses_zip_stored_not_deflate(tmp_path):
    src = _make_file(tmp_path, "video1.mp4")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    z.add_and_delete(src, "video1.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        info = zf.getinfo("video1.mp4")
        assert info.compress_type == zipfile.ZIP_STORED


def test_duplicate_filenames_get_a_collision_suffix(tmp_path):
    src1 = _make_file(tmp_path, "a.jpg", b"first")
    src2 = _make_file(tmp_path, "b.jpg", b"second")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    name1 = z.add_and_delete(src1, "photo.jpg")
    name2 = z.add_and_delete(src2, "photo.jpg")
    z.close()
    assert name1 == "photo.jpg"
    assert name2 == "photo (1).jpg"
    assert name1 != name2
    with zipfile.ZipFile(zip_path) as zf:
        assert set(zf.namelist()) == {"photo.jpg", "photo (1).jpg"}


def test_multiple_items_all_end_up_in_the_same_archive(tmp_path):
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    for i in range(5):
        src = _make_file(tmp_path, f"item{i}.mp4", f"content-{i}".encode())
        z.add_and_delete(src, f"item{i}.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert len(zf.namelist()) == 5


def test_a_failed_item_never_reaches_add_and_delete_and_leaves_the_zip_valid(tmp_path):
    # Simulates the batch loop's own contract: a download that raises never
    # calls add_and_delete at all for that item, so the archive just has one
    # fewer entry - it must still close as a valid, readable zip.
    src = _make_file(tmp_path, "ok.mp4")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    z.add_and_delete(src, "ok.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.testzip() is None
        assert zf.namelist() == ["ok.mp4"]


def test_touch_refreshes_the_zip_files_mtime(tmp_path):
    # final-review finding #3: this is the heartbeat that must keep zip_dir
    # fresh in reaper.py's mtime-based sweep even before any single item
    # finishes and gets add_and_delete()'d.
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    # Force the file artificially stale first, so a real clock advance isn't
    # needed - deterministic and instant, no time.sleep() required.
    old_time = 1_000_000
    os.utime(zip_path, (old_time, old_time))
    assert os.path.getmtime(zip_path) == old_time

    z.touch()

    assert os.path.getmtime(zip_path) > old_time
    z.close()


def test_touch_is_a_no_op_when_the_zip_file_is_missing(tmp_path):
    # Defensive: touch() must never raise even if the underlying file is
    # gone (e.g. a race with cleanup) - it swallows OSError.
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    z.close()
    os.remove(zip_path)
    z.touch()  # must not raise


# ---- ordering: entries must land in item order, not completion order ----


def test_indexed_items_land_in_index_order_even_when_finished_out_of_order(tmp_path):
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    for index in (2, 0, 1):  # finish order != item order
        src = _make_file(tmp_path, f"src{index}.jpg", f"content-{index}".encode())
        z.add_and_delete(src, f"slide{index}.jpg", index=index)
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["slide0.jpg", "slide1.jpg", "slide2.jpg"]
        assert zf.read("slide1.jpg") == b"content-1"


def test_an_item_is_held_back_until_every_earlier_item_is_resolved(tmp_path):
    z = BatchZipper(str(tmp_path / "batch.zip"))
    src1 = _make_file(tmp_path, "src1.jpg")
    z.add_and_delete(src1, "slide1.jpg", index=1)
    assert os.path.exists(src1)  # index 0 still outstanding - not written yet
    z.skip(0)  # item 0 failed: it must not block the rest of the batch
    assert not os.path.exists(src1)
    z.close()
    with zipfile.ZipFile(str(tmp_path / "batch.zip")) as zf:
        assert zf.namelist() == ["slide1.jpg"]


def test_close_flushes_held_items_when_a_gap_is_never_resolved(tmp_path):
    # e.g. a cancelled batch: an earlier item never reports back at all.
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    for index in (2, 1):
        src = _make_file(tmp_path, f"src{index}.jpg")
        z.add_and_delete(src, f"slide{index}.jpg", index=index)
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["slide1.jpg", "slide2.jpg"]
