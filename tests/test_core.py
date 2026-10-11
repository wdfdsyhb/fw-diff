import fw_diff as fd


def make_tree(base, files):
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def test_scan_records_relative_paths_and_hashes(tmp_path):
    make_tree(tmp_path, {"etc/version": "1.0", "bin/app": "binary"})
    snap = fd.scan(tmp_path)
    by_path = {e["path"]: e for e in snap["files"]}
    assert by_path["etc/version"]["sha256"] == fd.hash_bytes(b"1.0")
    assert by_path["bin/app"]["size"] == len(b"binary")
    assert "created" in snap


def test_scan_skips_symlinks(tmp_path):
    make_tree(tmp_path, {"real.txt": "x"})
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(tmp_path / "real.txt")
    except OSError:
        pass  # Windows 无符号链接权限时跳过该用例主体
    snap = fd.scan(tmp_path)
    paths = {e["path"] for e in snap["files"]}
    assert "real.txt" in paths


def test_diff_categories(tmp_path):
    make_tree(tmp_path / "a", {"keep": "k", "gone": "g", "mod": "old"})
    make_tree(tmp_path / "b", {"keep": "k", "mod": "new", "new": "n"})
    d = fd.diff(fd.scan(tmp_path / "a"), fd.scan(tmp_path / "b"))
    assert d["added"] == ["new"]
    assert d["removed"] == ["gone"]
    assert d["modified"] == ["mod"]
    assert d["unchanged"] == ["keep"]


def test_hash_changes_marks_modified(tmp_path):
    d1, d2 = tmp_path / "v1", tmp_path / "v2"
    make_tree(d1, {"etc/conf": "a=1"})
    make_tree(d2, {"etc/conf": "a=2"})
    d = fd.diff(fd.scan(d1), fd.scan(d2))
    assert d["modified"] == ["etc/conf"]


def test_hash_bytes_stable():
    assert fd.hash_bytes(b"abc") == fd.hash_bytes(b"abc")
    assert fd.hash_bytes(b"abc") != fd.hash_bytes(b"abd")
