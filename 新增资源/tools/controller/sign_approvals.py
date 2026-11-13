"""Record review approvals for candidates in a generated or local source directory.

Run this only for ids a human has visually reviewed. The signature binds the id to the exact
bytes of the main file and its companion files, so later edits invalidate the approval.
The output file lives outside the checkout and is passed to the controller with --approvals.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_knowledge_base_batch import read, signature, write  # noqa: E402


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", type=Path, required=True, help="Directory holding 资源描述.json and the files")
    cli.add_argument("--out", type=Path, required=True, help="Private approvals JSON; merged if it exists")
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--ids", type=Path, help="Text file, one reviewed id per line")
    group.add_argument("--all", action="store_true", help="Approve every row in the description file")
    cli.add_argument("--name-cleared", type=Path,
                     help="Text file of ids whose name-only collision with the old library was reviewed")
    args = cli.parse_args()
    root = args.root.resolve()
    rows = {r["id"]: r for r in read(root / "资源描述.json")}
    wanted = list(rows) if args.all else [
        line.strip() for line in args.ids.read_text(encoding="utf-8").splitlines() if line.strip()]
    missing = [i for i in wanted if i not in rows]
    if missing:
        cli.error(f"Unknown ids: {missing[:5]}")
    data = read(args.out) if args.out.exists() else {}
    data.setdefault("approved", {})
    data.setdefault("name_cleared", [])
    for asset_id in wanted:
        data["approved"][asset_id] = signature(root, rows[asset_id])
    if args.name_cleared:
        cleared = [l.strip() for l in args.name_cleared.read_text(encoding="utf-8").splitlines() if l.strip()]
        data["name_cleared"] = sorted(set(data["name_cleared"]) | set(cleared))
    write(args.out, data)
    print(f"signed {len(wanted)}; total approved {len(data['approved'])}")


if __name__ == "__main__":
    main()
