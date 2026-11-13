"""Run trusted, finite candidate packs through the existing PPT Toolbox pipeline."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from io import BytesIO
import xml.etree.ElementTree as ET


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    tmp.replace(path)


def inside(root, name):
    path = (root/name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Invalid pack file: {name}")
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root, row, pack):
    path = inside(root, row["file_path"])
    if row["license"] not in {"CC0-1.0", "Apache-2.0"}:
        raise ValueError("License needs review")
    if row["license"] == "CC0-1.0" and not pack.get("original_cc0"):
        raise ValueError("Missing original CC0 declaration")
    if row["license"] == "Apache-2.0":
        if not (row.get("source_url","").startswith("https://") and row.get("author")
                and row.get("license_url","").startswith("https://")):
            raise ValueError("Missing attribution")
        if not any("Apache License" in inside(root,n).read_text(encoding="utf-8")
                   for n in pack.get("documents",[]) if "LICENSE" in n):
            raise ValueError("Missing Apache license text")
    if not row.get("motif_key") or not row.get("name_zh"):
        raise ValueError("Missing resource description")
    extras = [inside(root,n) for n in row.get("extra_paths",[])]
    if path.suffix == ".svg":
        raw = path.read_bytes()
        if len(raw)>5_000_000 or re.search(rb'<!DOCTYPE|<!ENTITY|<\?',raw,re.I):
            raise ValueError("Unsafe SVG declaration")
        svg = ET.fromstring(raw)
        box = list(map(float,svg.attrib["viewBox"].split()))
        if len(box)!=4 or not all(abs(n)<100000 for n in box) or min(box[2:])<=0:
            raise ValueError("Invalid viewBox")
        for node in svg.iter():
            if node.tag.split("}")[-1] in {"script","style","foreignObject","image","use","a","animate","set"}:
                raise ValueError("Unsupported SVG element")
            if any(k.split("}")[-1].lower().startswith(("on","href")) or "url(" in v.lower()
                   for k,v in node.attrib.items()):
                raise ValueError("Unsupported SVG reference")
        if row["category"]=="配色":
            colors = read(next(p for p in extras if p.suffix==".json"))["colors"]
            if not 3<=len(colors)<=16 or len(colors)!=len(set(colors)) or any(
                    not re.fullmatch(r"#[0-9A-Fa-f]{6}",c) for c in colors):
                raise ValueError("Invalid palette")
            swatches = {n.get("fill","").upper() for n in svg.findall(".//{*}rect")}
            if not set(map(str.upper,colors))<=swatches or len(row.get("keywords_zh",[]))<2:
                raise ValueError("Missing swatches or usage metadata")
    elif path.suffix == ".pptx":
        with ZipFile(path) as z:
            names = z.namelist()
            if any(n.lower().endswith((".bin",".exe")) for n in names):
                raise ValueError("Unexpected executable or embedded object")
            for n in names:
                if n.endswith(".rels"):
                    rels = ET.fromstring(z.read(n))
                    if any(rel.get("TargetMode") == "External" for rel in rels):
                        raise ValueError("External PPTX relationship requires review")
            slide = ET.fromstring(z.read("ppt/slides/slide1.xml"))
            if len(slide.findall(".//{*}sp"))<3 or slide.findall(".//{*}pic"):
                raise ValueError("Missing native objects")
            for n in names:
                if re.fullmatch(r"ppt/charts/chart\d+\.xml",n):
                    chart = ET.fromstring(z.read(n))
                    if chart.find(".//{*}externalData") is None:
                        raise ValueError("Chart lacks editable data link")
                    books = [b for b in names if b.startswith("ppt/embeddings/") and b.endswith(".xlsx")]
                    if not books:
                        raise ValueError("Missing workbook")
                    for book in books:
                        with ZipFile(BytesIO(z.read(book))) as workbook:
                            sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
                            if len(sheet.findall(".//{*}c"))<4:
                                raise ValueError("Empty workbook")
        row["powerpoint_app_verification"] = "未完成 PowerPoint 实测"
    else:
        raise ValueError("Unsupported format for automatic admission")
    # Approval binds the full payload to a human-reviewed pack, including companion bytes.
    signature = hashlib.sha256("\n".join(sha(p) for p in [path,*extras]).encode()).hexdigest()
    if pack.get("approved",{}).get(row["id"]) != signature:
        raise ValueError("Visual or design review required")
    return sha(path)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("repo","baseline","plan","state"):
        cli.add_argument("--"+name, type=Path, required=True)
    cli.add_argument("--target", type=int, default=1000)
    cli.add_argument("--category", action="append")
    cli.add_argument("--batch-size", type=int, default=50)
    cli.add_argument("--remote", default="origin")
    cli.add_argument("--branch", default="main")
    args = cli.parse_args()
    repo, baseline, plan, status = (getattr(args,n).resolve() for n in ("repo","baseline","plan","state"))
    if status.is_relative_to(repo) or baseline.is_relative_to(repo):
        cli.error("Keep private baseline and run state outside the publication checkout.")
    if not 1<=args.batch_size<=50 or args.target<1:
        cli.error("Batch size must be 1–50 and target must be positive.")
    status.parent.mkdir(parents=True,exist_ok=True)
    lock = sqlite3.connect(status.with_suffix(".lock.sqlite"),timeout=0)
    lock.execute("BEGIN EXCLUSIVE")
    env = dict(os.environ,GIT_TERMINAL_PROMPT="0",PYTHONUTF8="1")

    def git(*cmd, timeout=120):
        return subprocess.check_output(["git","-C",str(repo),*cmd],env=env,timeout=timeout).decode().strip()

    ref = "refs/heads/"+args.branch
    def remote_head():
        return git("ls-remote","--exit-code",args.remote,ref).split()[0]

    target = repo/"新增资源"
    catalog = target/"增量索引.json"
    progress = target/"任务状态.json"
    tools = target/"tools"
    settings = dict(repo=str(repo), baseline=sha(baseline), plan=sha(plan), goal=args.target,
                    category=args.category, remote=git("remote","get-url",args.remote),branch=args.branch)
    if not status.exists():
        if git("status","--porcelain") or git("rev-parse","HEAD")!=remote_head():
            raise RuntimeError("Start from a clean checkout synchronized to the remote.")
        write(status,dict(settings=settings,completed=0,commits=[],pending=None))
    state = read(status)
    if state["settings"]!=settings:
        raise RuntimeError("Resume with the same inputs, or use a new state file.")
    if git("symbolic-ref","HEAD")!=ref:
        raise RuntimeError("Unexpected local branch")
    def save():
        write(status,state)

    def recover():
        pending = state["pending"]
        if not pending:
            return
        head = git("rev-parse","HEAD")
        batch_path = "新增资源/batch-"+pending["batch"]
        if head==pending["base"]:
            # This checkout was clean before the journal was written.
            git("restore","--source=HEAD","--staged","--worktree","--",
                "新增资源/增量索引.json","新增资源/任务状态.json")
            git("reset","--quiet","HEAD","--",batch_path)
            if (repo/batch_path).is_dir():
                shutil.rmtree(repo/batch_path)
        else:
            if git("rev-parse","HEAD^")!=pending["base"] or git("log","-1","--format=%s")!=pending["message"]:
                raise RuntimeError("Unexpected HEAD; keep the journal for manual recovery")
            for attempt in range(3):
                try:
                    actual = remote_head()
                    if actual!=head:
                        if actual!=pending["base"]:
                            raise RuntimeError("Remote advanced; preserve local commit for review")
                        git("push",args.remote,f"HEAD:{ref}")
                        if remote_head()!=head:
                            raise RuntimeError("Remote verification failed")
                    break
                except (subprocess.SubprocessError,OSError):
                    if attempt==2:
                        raise
                    time.sleep(2**attempt)
            state["completed"]+=pending["count"]
            state["commits"].append(dict(batch=pending["batch"],commit=head,count=pending["count"]))
        state["pending"]=None
        save()

    recover()
    if git("status","--porcelain") or git("rev-parse","HEAD")!=remote_head():
        raise RuntimeError("Checkout must remain clean and synchronized.")
    if state["completed"]>=args.target:
        return
    stats = Counter()
    by_category = Counter()
    with TemporaryDirectory(prefix="ppt-production-") as tmp:
        stage = Path(tmp)
        packs = read(plan)["packs"]
        candidates=[]
        for i,pack in enumerate(packs):
            root=stage/str(i)
            root.mkdir()
            if "command" in pack:
                command=[part.replace("{out}",str(root)).replace("{plan}",str(plan.parent))
                         for part in pack["command"]]
                subprocess.run(command,cwd=plan.parent,env=env,check=True,timeout=900)
            else:
                shutil.copytree((plan.parent/pack["directory"]).resolve(),root,dirs_exist_ok=True)
            for row in read(root/"资源描述.json"):
                if not args.category or row["category"] in args.category:
                    candidates.append((root,pack,row))
        prior = read(catalog)["assets"]
        known = {r["id"] for r in prior}
        hashes = {r["sha256"] for r in prior}
        motifs = {r.get("motif_key") for r in prior}
        prepared=[]
        pending_review=[]
        for root,pack,row in candidates:
            stats["candidates"]+=1
            try:
                path = inside(root,row["file_path"])
                digest = sha(path)
                if row["id"] in known or digest in hashes or row.get("motif_key") in motifs:
                    stats["duplicate"]+=1
                    continue
                digest=validate(root,row,pack)
            except (ValueError,KeyError,StopIteration,ET.ParseError,OSError):
                stats["review_or_invalid"]+=1
                pending_review.append(row.get("id"))
                continue
            stats["validated"]+=1
            known.add(row["id"])
            hashes.add(digest)
            motifs.add(row["motif_key"])
            row["sha256"]=digest
            prepared.append((root,pack,row))
        write(stage/"candidates.json",[row for _,_,row in prepared])
        subprocess.run([sys.executable,str(tools/"audit.py"),str(baseline),
                        str(stage/"candidates.json"),"--accepted",str(catalog),
                        "--out",str(stage/"audit.json")],env=env,check=True)
        checked=read(stage/"audit.json")["results"]
        accepted=[]
        for (root,pack,row),review in zip(prepared,checked,strict=True):
            if review["status"]!="pending_review":
                stats["duplicate"]+=1
            elif any(review[k]["content"] for k in ("baseline","accepted_additions","earlier_candidates")):
                stats["review_or_invalid"]+=1
                pending_review.append(row["id"])
            else:
                accepted.append((root,pack,row))
                by_category[row["category"]]+=1
        state.update(stats=dict(stats),eligible_by_category=dict(by_category),review_ids=pending_review)
        save()
        while accepted and state["completed"]<args.target:
            size=min(args.batch_size,args.target-state["completed"])
            batch=read(progress)["next_batch"]
            payload=stage/"payload"
            payload.mkdir()
            rows=[]
            for i,(root,pack,row) in enumerate(accepted[:size]):
                row=dict(row)
                prefix=f"item-{i+1:03}"
                for key,names in (("file_path",[row["file_path"]]),("extra_paths",row.get("extra_paths",[]))):
                    output=[]
                    for n in names:
                        dest=payload/prefix/n
                        if not dest.resolve().is_relative_to((payload/prefix).resolve()):
                            raise ValueError("Unsafe publication path")
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(inside(root,n),dest)
                        output.append(dest.relative_to(payload).as_posix())
                    row[key]=output[0] if key=="file_path" else output
                for n in pack.get("documents",[]):
                    source=inside(root,n)
                    shutil.copyfile(source,payload/prefix/source.name)
                    row["extra_paths"].append(f"{prefix}/{source.name}")
                rows.append(row)
            write(payload/"资源描述.json",rows)
            base=git("rev-parse","HEAD")
            message=f"Publish automated PPT batch {batch}"
            destination=target/f"batch-{batch}"
            if destination.exists() or remote_head()!=base:
                raise RuntimeError("Batch path exists or remote moved")
            state["pending"]=dict(base=base,batch=batch,count=len(rows),message=message)
            save()
            shutil.move(str(payload),destination)
            subprocess.run([sys.executable,str(tools/"finalize.py"),str(target),batch,str(baseline)],
                           env=env,check=True)
            git("add","--",str(destination),str(catalog),str(progress))
            git("diff","--cached","--check")
            git("-c","commit.gpgsign=false","commit","-m",message)
            recover()
            del accepted[:size]
    state["result"]="target_reached" if state["completed"]>=args.target else "candidate_pool_exhausted"
    state["shortfall"]=args.target-state["completed"]
    save()
    print(json.dumps(state,ensure_ascii=False,indent=2))
    lock.close()


if __name__=="__main__":
    main()
