#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fw-diff - snapshot & diff unpacked firmware rootfs trees.

Scan a firmware extraction (binwalk output, mounted rootfs, dumped squashfs)
into a JSON manifest, then diff two manifests: what files appeared, vanished,
or changed between firmware versions. The fastest way to see what an update
actually touches - or what a vendor quietly added.

Zero third-party dependencies.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.1.0"

DEFAULT_HASH_LIMIT = 8 * 1024 * 1024  # skip hashing files above this (bytes)


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def scan(root, hash_limit=DEFAULT_HASH_LIMIT):
    """Walk a tree (no symlink following) into a file manifest with SHA-256."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    files = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError as e:
            sys.stderr.write(f"fw-diff: skip unreadable dir {d}: {e}\n")
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                p = Path(entry.path)
                size = entry.stat(follow_symlinks=False).st_size
                digest = ""
                if size <= hash_limit:
                    try:
                        digest = hash_bytes(p.read_bytes())
                    except OSError as e:
                        sys.stderr.write(f"fw-diff: unreadable file {p}: {e}\n")
                files.append({"path": p.relative_to(root).as_posix(),
                              "size": size, "sha256": digest})
    files.sort(key=lambda e: e["path"])
    return {"schema": 1, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "root": str(root), "files": files}


def diff(old, new):
    o = {e["path"]: e for e in old["files"]}
    n = {e["path"]: e for e in new["files"]}
    added = sorted(set(n) - set(o))
    removed = sorted(set(o) - set(n))
    modified = sorted(
        p for p in set(o) & set(n)
        if o[p]["sha256"] != n[p]["sha256"]
        or (not o[p]["sha256"] and o[p]["size"] != n[p]["size"]))
    unchanged = sorted(p for p in set(o) & set(n) if p not in set(modified))
    return {"added": added, "removed": removed, "modified": modified, "unchanged": unchanged}


def render(d, old_root="", new_root=""):
    lines = []
    for label, items in (("NEW", d["added"]), ("GONE", d["removed"]), ("CHANGED", d["modified"])):
        lines.append(f"[{label}] {len(items)}")
        for p in items:
            lines.append(f"  {p}")
    lines.append(f"[same] {len(d['unchanged'])}")
    if old_root or new_root:
        lines.append(f"({old_root or '?'} -> {new_root or '?'})")
    return "\n".join(lines)


def load_manifest(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(d.get("files"), list):
        raise SystemExit(f"not a fw-diff manifest (no files list): {path}")
    return d


def to_json(manifest):
    return json.dumps(manifest, ensure_ascii=False, indent=2)


EXAMPLES = """examples:
  fw-diff scan ./rootfs-v1 -o v1.json
  fw-diff scan ./rootfs-v2 -o v2.json
  fw-diff diff v1.json v2.json            # what did this update change?
  fw-diff diff v1.json v2.json --csv changes.csv
"""


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="fw-diff", description=__doc__.strip().splitlines()[0],
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="snapshot a rootfs tree into a JSON manifest")
    p_scan.add_argument("root", help="directory tree to scan")
    p_scan.add_argument("-o", "--out", required=True, help="manifest .json to write")
    p_scan.add_argument("--hash-limit", type=int, default=DEFAULT_HASH_LIMIT,
                        help="skip SHA-256 for files above this size, bytes (default 8388608)")

    p_diff = sub.add_parser("diff", help="diff two manifests")
    p_diff.add_argument("old", help="older manifest .json")
    p_diff.add_argument("new", help="newer manifest .json")
    p_diff.add_argument("--csv", dest="csv_out", help="write changes (added+removed+modified) to CSV")
    p_diff.add_argument("--fail", action="store_true", help="exit code 2 if anything changed")

    ap.add_argument("-V", "--version", action="version", version=f"fw-diff {__version__}")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if args.cmd == "scan":
        manifest = scan(args.root, hash_limit=args.hash_limit)
        Path(args.out).expanduser().write_text(to_json(manifest), encoding="utf-8")
        print(f"scanned {len(manifest['files'])} files -> {args.out}", file=sys.stderr)
        return 0

    d = diff(load_manifest(args.old), load_manifest(args.new))
    print(render(d, args.old, args.new))
    if args.csv_out:
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["change", "path"])
        for label, items in (("added", d["added"]), ("removed", d["removed"]), ("modified", d["modified"])):
            for p in items:
                w.writerow([label, p])
        Path(args.csv_out).expanduser().write_text(buf.getvalue(), encoding="utf-8")
    return 2 if (args.fail and (d["added"] or d["removed"] or d["modified"])) else 0


if __name__ == "__main__":
    sys.exit(main())
