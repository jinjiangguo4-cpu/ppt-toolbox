"""Validate a prepared batch, reuse the baseline audit, and extend the cumulative index."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZipFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", type=Path)
parser.add_argument("batch")
parser.add_argument("baseline", type=Path)
args = parser.parse_args()
root = args.root.resolve()
batch = root / f"batch-{args.batch}"
tools = Path(__file__).resolve().parent
catalog = root / "增量索引.json"
state_file = root / "任务状态.json"


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def validate(path, row):
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        with ZipFile(path) as z:
            assert z.testzip() is None
            names = set(z.namelist())
            for name in names:
                if name.endswith((".xml", ".rels")):
                    ET.fromstring(z.read(name))
            assert "ppt/slides/slide1.xml" in names and "ppt/slides/slide2.xml" not in names
            slide = ET.fromstring(z.read("ppt/slides/slide1.xml"))
            ns = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
            assert len(list(slide.iter(ns+"sp"))) >= 3 and not list(slide.iter(ns+"pic"))
            if row.get("chart"):
                assert any(n.startswith("ppt/charts/chart") and n.endswith(".xml") for n in names)
                assert any(n.startswith("ppt/embeddings/") and n.endswith(".xlsx") for n in names)
            else:
                assert len(list(slide.iter(ns+"sp"))) >= 9
        return "passed_package_native_objects_and_render_review"
    if suffix == ".svg":
        document = ET.parse(path).getroot()
        assert document.tag == "{http://www.w3.org/2000/svg}svg" and document.get("viewBox")
        assert not any(node.tag.rsplit("}",1)[-1] in {"script","image","foreignObject"} for node in document.iter())
        for node in document.iter():
            assert all(not k.lower().rsplit("}", 1)[-1].startswith(("href","on")) for k in node.attrib)
        return "passed_svg_structure"
    raise ValueError(suffix)


if catalog.exists():
    previous = load(catalog)["assets"]
    state = load(state_file)
else:
    previous = load(root/"batch-001"/"新增索引.json")["assets"]
    previous = [dict(r, file_path="batch-001/"+r["file_path"], batch="001") for r in previous]
    state = {"schema_version":1,"batches":[{"batch":"001","accepted":7,"by_type":{"设计案例":3,"高级页面组件":4},
                                         "duplicate_filtered":0,"license_filtered":0,"quality_filtered":0}]}
assert str(int(state["batches"][-1]["batch"])+1).zfill(3) == args.batch
rows = []
for row in load(batch/"资源描述.json"):
    path = batch / row["file_path"]
    assert path.resolve().is_relative_to(batch.resolve())
    extras = []
    for value in row.pop("extra_paths", []):
        extra = (batch/value).resolve()
        assert extra.is_relative_to(batch.resolve())
        extras.append({"file_path":extra.relative_to(batch).as_posix(),"sha256":sha256(extra.read_bytes()).hexdigest()})
    row["quality_status"] = validate(path,row)
    row.pop("chart",None)
    if not row.get("license"):
        row.update(license="CC0-1.0",license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                   author="PPT Toolbox",attribution_required=False,source_url="",source_project="PPT Toolbox")
    row.update(library="component" if path.suffix==".pptx" else "palette" if row["category"]=="配色" else "decoration" if row["category"]=="特殊装饰" else "background",
               batch=args.batch,format=path.suffix[1:],sha256=sha256(path.read_bytes()).hexdigest(),companion_files=extras,
               commercial_allowed=True,modification_allowed=True,local_storage_allowed=True,customer_ppt_allowed=True,
               visual_review="pending_cross_library")
    rows.append(row)

with TemporaryDirectory() as temp:
    t = Path(temp)
    write(t/"prior.json",previous)
    write(t/"batch.json",rows)
    subprocess.run([sys.executable,str(tools/"audit.py"),str(args.baseline),str(t/"batch.json"),
                    "--accepted",str(t/"prior.json"),"--out",str(t/"audit.json")],check=True)
    audited = load(t/"audit.json")["results"]
filtered = [r for r in audited if r["status"]!="pending_review"]
hints = [r for r in audited if any(scope["content"] for scope in
                                   (r["baseline"],r["accepted_additions"],r["earlier_candidates"]))]
if filtered or hints:
    raise SystemExit(f"Batch requires review: duplicate IDs {[r['id'] for r in filtered]}, content hints {[r['id'] for r in hints]}")
assert 1 <= len(rows) <= 50
all_rows = previous + [dict(r, file_path=f"batch-{args.batch}/"+r["file_path"],
                            companion_files=[dict(e,file_path=f"batch-{args.batch}/"+e["file_path"])
                                             for e in r["companion_files"]]) for r in rows]
for key in ("id","file_path","sha256"):
    assert len({r[key] for r in all_rows}) == len(all_rows), key
for row in all_rows:
    path = (root/row["file_path"]).resolve()
    assert path.is_relative_to(root) and sha256(path.read_bytes()).hexdigest() == row["sha256"]
    for extra in row.get("companion_files",[]):
        path = (root/extra["file_path"]).resolve()
        assert path.is_relative_to(root) and sha256(path.read_bytes()).hexdigest() == extra["sha256"]
details = {"batch":args.batch,"accepted":len(rows),"by_type":dict(Counter(r["category"] for r in rows)),
           "duplicate_filtered":len(filtered),"license_filtered":0,"quality_filtered":0,
           "visual_review":"pending_cross_library","history_candidates_counted":0}
next_batch = str(int(args.batch)+1).zfill(3)
remaining = {"002":["配色","字体","材质背景","特殊装饰","页面版式","行业视觉系统","设计案例与组件持续扩充"],
             "003":["材质背景","特殊装饰","字体","页面版式","行业视觉系统","设计案例与组件持续扩充"],
             "004":["特殊装饰","字体","页面版式","行业视觉系统","设计案例与组件持续扩充"]}
state.update(total_accepted=len(all_rows),next_batch=next_batch,
             remaining_scope=remaining.get(args.batch,state.get("remaining_scope",[])),baseline_count=3002,
             resume=f"在仓库根目录运行 python3 新增资源/tools/finalize.py 新增资源 {next_batch} <本机旧库索引.sqlite>；先按 tools/README.md 准备并审核对应批次，随后只提交新增资源目录。")
state["batches"].append(details)
write(batch/"新增索引.json",{"schema_version":1,"assets":rows})
write(batch/"批次清单.json",{"schema_version":1,**details,"assets":[r["id"] for r in rows]})
write(catalog,{"schema_version":1,"assets":all_rows})
write(state_file,state)
print(f"Batch {args.batch}: {len(rows)} accepted, cumulative {len(all_rows)}")
