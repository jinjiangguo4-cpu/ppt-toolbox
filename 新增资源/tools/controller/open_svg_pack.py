"""Adapt pinned Tabler npm archives by upstream category without extracting archives."""
import argparse
import json
from pathlib import Path
import re
import tarfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("archive",type=Path)
parser.add_argument("category")
parser.add_argument("out",type=Path)
args=parser.parse_args()
with tarfile.open(args.archive,"r:gz") as archive:
    metadata=json.load(archive.extractfile("package/package.json"))
    if metadata["name"]!="@tabler/icons" or metadata["license"]!="MIT":
        raise ValueError("Expected official Tabler package with MIT license")
    license_text=archive.extractfile("package/LICENSE").read()
    (args.out/"Tabler-LICENSE.txt").write_bytes(license_text)
    version=metadata["version"]
    rows=[]
    prefix=f"package/categories/outline/{args.category}/"
    folder=args.out/"icons"
    folder.mkdir()
    for member in sorted(archive.getmembers(),key=lambda member:member.name):
        if not member.isfile() or not member.name.startswith(prefix):
            continue
        name=member.name.removeprefix(prefix)
        if not re.fullmatch(r"[a-z][a-z0-9-]*\.svg",name) or member.size>100_000:
            continue
        slug=name[:-4]
        if re.search(r"-(off|filled|[0-9]+)$",slug):
            continue
        (folder/name).write_bytes(archive.extractfile(member).read())
        base=f"https://github.com/tabler/tabler-icons/blob/v{version}"
        rows.append(dict(id=f"tabler-outline-{slug}",name_zh=f"{slug} 图标",
                         name_en=slug.replace("-"," "),category="特殊装饰",subcategory=args.category,
                         motif_key=f"tabler-outline-{slug}",file_path=f"icons/{name}",license="MIT",
                         author="Paweł Kuna and Tabler contributors",source_project="Tabler Icons",
                         original_resource_id=f"outline/{slug}",source_url=f"{base}/icons/outline/{name}",
                         license_url=f"{base}/LICENSE",editability="SVG-path-editable"))
    (args.out/"资源描述.json").write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
