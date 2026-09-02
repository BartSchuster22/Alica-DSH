#!/usr/bin/env python3
"""Translate authenticated offline image references to Docker-local tags."""
import json
import pathlib
import sys


def entries(path: str):
    data = json.load(open(path, encoding="utf-8"))["images"]
    for item in data:
        ref = item["reference"]
        image_id = item["imageId"]
        digest = item["digest"]
        assert ref.endswith("@" + digest)
        assert image_id.startswith("sha256:") and len(image_id) == 71
        repo = ref.rsplit("@", 1)[0]
        yield ref, image_id, f"{repo}:d6-offline-{digest[7:19]}"


def main():
    mode, image_map = sys.argv[1:3]
    if mode == "resolve":
        requested = sys.argv[3]
        for ref, image_id, tag in entries(image_map):
            if ref == requested:
                print(image_id, tag, sep="\t")
                return
        raise SystemExit(1)
    if mode == "rewrite":
        target = pathlib.Path(sys.argv[3])
        original = target.read_text()
        updated = original
        for ref, _, tag in entries(image_map):
            updated = updated.replace(ref, tag)
        if updated == original:
            raise SystemExit("no immutable image references found in compose environment")
        target.write_text(updated)
        return
    raise SystemExit(2)


if __name__ == "__main__":
    main()
