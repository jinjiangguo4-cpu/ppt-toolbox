"""Read-only PPT asset cross-library audit. Outputs IDs and aggregate counts only."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sqlite3
from unicodedata import normalize
from urllib.parse import parse_qsl, urlencode, urlsplit

HEX = re.compile(r"[0-9a-f]{64}")


def hashes(row):
    return {str(row.get(key) or "").strip().lower()
            for key in (("file_sha256",) if row.get("file_sha256") else ("sha256",))
            if not (row.get("source_page") and str(row.get("format", "")).lower() == "pptx")
            if HEX.fullmatch(str(row.get(key) or "").strip().lower())}


def label(value):
    return ''.join(c for c in normalize("NFKC", str(value or "")).casefold() if c.isalnum())


def url_key(value):
    url = urlsplit(str(value or "").strip())
    if url.scheme not in ("http", "https") or not url.hostname:
        return ""
    query = urlencode(sorted((k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
                             if not k.lower().startswith("utm_")))
    return (url.hostname.lower().removeprefix("www."), url.path.rstrip("/"), query, url.fragment)


def load_json(path):
    data = json.loads(path.read_text())
    return data["assets"] if isinstance(data, dict) else data


def source_keys(row):
    url = url_key(row.get("source_url") or row.get("source"))
    page = row.get("source_page")
    shape = row.get("source_shape_id") or row.get("copy_top_level_id")
    project = label(row.get("source_project"))
    keys = set()
    if url:
        keys.add(("url", url, str(page or ""), str(shape or "")))
    if project and page is not None and page != "":
        keys.add(("project-page", project, str(page), str(shape or "")))
    if row.get("original_resource_id") and url:
        keys.add(("source-id", url[0], row["original_resource_id"]))
    return keys


def index_add(maps, row):
    asset_id = row["id"]
    for key in hashes(row):
        maps["file"][key].add(asset_id)
    for key in source_keys(row):
        maps["source"][key].add(asset_id)
    for field in ("motif_key", "name_zh", "name_en", "name"):
        key = label(row.get(field))
        if key:
            maps["content"][key].add(asset_id)


def lookup(maps, row):
    matches = {}
    for level, keys in (("file", hashes(row)), ("source", source_keys(row)),
                        ("content", {label(row.get(k)) for k in
                                     ("motif_key", "name_zh", "name_en", "name")} - {""})):
        matches[level] = sorted({hit for key in keys for hit in maps[level].get(key, ())})
    return matches


def visual_hash(root, row):
    if root is None:
        return None
    from PIL import Image, ImageOps
    value = row.get("path") or row.get("file_path")
    if not value or Path(value).is_absolute():
        return None
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        return None
    try:
        with Image.open(path) as source:
            im = source.convert("RGBA")
            box = im.getchannel("A").getbbox()
            if not box:
                return None
            im = im.crop(box)
            background = Image.new("RGBA", im.size, "white")
            background.alpha_composite(im)
            px = list(ImageOps.grayscale(background).resize((9, 8), Image.Resampling.LANCZOS).getdata())
            return sum((px[y*9+x] > px[y*9+x+1]) << (y*8+x)
                       for y in range(8) for x in range(8))
    except (OSError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--accepted", type=Path, help="Index of already accepted additions")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--baseline-images", type=Path)
    parser.add_argument("--candidate-images", type=Path)
    parser.add_argument("--accepted-images", type=Path)
    args = parser.parse_args()
    if args.baseline.suffix == ".sqlite":
        with sqlite3.connect(args.baseline.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(row) for row in db.execute("SELECT * FROM assets")]
            provenance = {row["source_id"]: dict(row) for row in db.execute(
                "SELECT source_id, status, asset_id FROM toolbox_import_status")}
    else:
        rows, provenance = load_json(args.baseline), {}
    if len(rows) != 3002 or len({r["id"] for r in rows if r.get("id")}) != 3002:
        raise SystemExit("Baseline must contain 3002 unique non-empty IDs.")
    old, added, seen = ({k: defaultdict(set) for k in ("file", "source", "content")} for _ in range(3))
    for row in rows:
        index_add(old, row)
    accepted_rows = load_json(args.accepted) if args.accepted else []
    if args.accepted:
        for row in accepted_rows:
            index_add(added, row)
    old_ids = {r["id"] for r in rows}
    visual = []
    for root, dataset in ((args.baseline_images, rows), (args.accepted_images, accepted_rows)):
        visual.append([(row["id"], signature) for row in dataset
                       if (signature := visual_hash(root, row)) is not None])
    baseline_visual_count = len(visual[0])
    accepted_visual_count = len(visual[1])
    visual.append([])
    results = []
    for row in load_json(args.candidates):
        prior = provenance.get(row["id"], {})
        previous, additions, batch = (lookup(index, row) for index in (old, added, seen))
        if prior.get("status") == "blocked":
            status = "blocked_prior_review"
        elif (prior.get("status") == "imported" and prior.get("asset_id") in old_ids
              or row["id"] in old_ids or previous["file"] or previous["source"]):
            status = "duplicate_baseline"
        elif additions["file"] or additions["source"] or batch["file"] or batch["source"]:
            status = "duplicate_additions_or_batch"
        else:
            status = "pending_review"
        signature = visual_hash(args.candidate_images, row)
        similar = []
        if signature is not None:
            for scope, entries in zip(("baseline", "accepted_additions", "earlier_candidates"), visual):
                similar.extend({"scope": scope, "id": asset_id, "distance": distance}
                               for asset_id, other in entries
                               if (distance := (signature ^ other).bit_count()) <= 6)
            visual[2].append((row["id"], signature))
        results.append(dict(id=row["id"], status=status, baseline=previous,
                            accepted_additions=additions, earlier_candidates=batch,
                            provenance_status=prior.get("status"),
                            visual_status="compared_available_images" if signature is not None else "not_compared",
                            visual_matches=similar))
        index_add(seen, row)
    report = {"baseline_count": len(rows), "candidate_count": len(results),
              "baseline_visual_count": baseline_visual_count,
              "accepted_visual_count": accepted_visual_count,
              "candidate_visual_count": len(visual[2]),
              "baseline_types": dict(Counter(r["library"] for r in rows)),
              "statuses": dict(Counter(r["status"] for r in results)),
              "results": results}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print({k: v for k, v in report.items() if k != "results"})


if __name__ == "__main__":
    main()
