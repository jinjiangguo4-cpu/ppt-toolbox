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


def signature(root, row):
    """Approval signature: SHA-256 over LF-joined payload hashes (main file, then extra_paths)."""
    files = [inside(root, row["file_path"]), *[inside(root, n) for n in row.get("extra_paths", [])]]
    return hashlib.sha256("\n".join(sha(p) for p in files).encode()).hexdigest()


def load_approvals(paths):
    """Merge private approval files: flat {id: signature} or {"approved": {...}, "name_cleared": [ids]}."""
    approved, cleared = {}, set()
    for path in paths or []:
        data = read(path)
        if "approved" in data or "name_cleared" in data:
            approved.update(data.get("approved", {}))
            cleared.update(data.get("name_cleared", []))
        else:
            approved.update(data)
    return approved, cleared


def validate(root, row, pack, supply_only=False, approved=None):
    path = inside(root, row["file_path"])
    if row["license"] not in {"CC0-1.0", "Apache-2.0", "MIT"}:
        raise ValueError("License needs review")
    if row["license"] == "CC0-1.0" and not pack.get("original_cc0"):
        raise ValueError("Missing original CC0 declaration")
    if row["license"] in {"Apache-2.0", "MIT"}:
        if not (row.get("source_url","").startswith("https://") and row.get("author")
                and row.get("license_url","").startswith("https://")):
            raise ValueError("Missing attribution")
        marker = {"Apache-2.0": "Apache License", "MIT": "Permission is hereby granted"}[row["license"]]
        if not any(marker in inside(root,n).read_text(encoding="utf-8")
                   for n in pack.get("documents",[]) if "LICENSE" in n):
            raise ValueError("Missing license text")
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
    expected = signature(root, row)
    if not supply_only and {**pack.get("approved",{}),**(approved or {})}.get(row["id"]) != expected:
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
    cli.add_argument("--supply-only", action="store_true")
    cli.add_argument("--approvals", type=Path, action="append",
                     help="Private approval file kept outside the checkout; changing it never invalidates run state.")
    args = cli.parse_args()
    repo, baseline, plan, status = (getattr(args,n).resolve() for n in ("repo","baseline","plan","state"))
    if status.is_relative_to(repo) or baseline.is_relative_to(repo):
        cli.error("Keep private baseline and run state outside the publication checkout.")
    if not 1<=args.batch_size<=50 or args.target<1:
        cli.error("Batch size must be 1–50 and target must be positive.")
    approval_files = [p.resolve() for p in args.approvals or []]
    if any(p.is_relative_to(repo) for p in approval_files):
        cli.error("Keep approval files outside the publication checkout.")
    approved_map, name_cleared = load_approvals(approval_files)
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
                    category=args.category, supply_only=args.supply_only, remote=git("remote","get-url",args.remote),branch=args.branch)
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
            counts=Counter(state.get("published_by_category",{}))
            counts.update(pending.get("by_category",{}))
            state["published_by_category"]=dict(counts)
            state["commits"].append(dict(batch=pending["batch"],commit=head,count=pending["count"]))
        state["pending"]=None
        save()

    recover()
    if git("status","--porcelain") or git("rev-parse","HEAD")!=remote_head():
        raise RuntimeError("Checkout must remain clean and synchronized.")
    if state["completed"]>=args.target:
        return
    # Stats describe this invocation only; sources are rescanned on every restart.
    stats = Counter()
    by_category = Counter()
    review_log = state.setdefault("review",{})
    configuration=read(plan)
    sources=configuration.get("sources",configuration.get("packs",[]))
    limits=configuration.get("categories",{})
    state.setdefault("published_by_category",{})
    if len({str(pack.get("id",i)) for i,pack in enumerate(sources)})!=len(sources):
        raise ValueError("Duplicate source IDs")
    history=state.setdefault("source_history",{})
    for source_index, pack in enumerate(sources):
        source_id=str(pack.get("id",source_index))
        # Only fully consumed sources are skipped. Failed or partly unresolved sources are retried,
        # so late-generated files, new approvals and cleared name collisions are picked up on restart.
        if history.get(source_id,{}).get("status")=="complete" or state["completed"]>=args.target:
            continue
        try:
            with TemporaryDirectory(prefix="ppt-production-") as tmp:
                stage = Path(tmp)
                packs = [pack]
                candidates=[]
                unresolved={}
                for i,pack in enumerate(packs):
                    root=stage/str(i)
                    root.mkdir()
                    cached=status.parent/(status.stem+".sources")/re.sub(r"[^A-Za-z0-9_-]","_",source_id)
                    if "command" in pack and cached.exists():
                        shutil.copytree(cached,root,dirs_exist_ok=True)
                    elif "command" in pack:
                        command=[part.replace("{out}",str(root)).replace("{plan}",str(plan.parent))
                                 for part in pack["command"]]
                        subprocess.run(command,cwd=plan.parent,env=env,check=True,timeout=900)
                    else:
                        shutil.copytree((plan.parent/pack["directory"]).resolve(),root,dirs_exist_ok=True)
                    descriptions=read(root/"资源描述.json")
                    if "command" in pack and not cached.exists():
                        cached.parent.mkdir(parents=True,exist_ok=True)
                        incoming=cached.parent/(cached.name+".incoming")
                        if incoming.exists():
                            shutil.rmtree(incoming)
                        shutil.copytree(root,incoming)
                        incoming.rename(cached)
                    for row in descriptions:
                        if not isinstance(row,dict) or not row.get("id") or not row.get("category"):
                            stats["review_or_invalid"]+=1
                            unresolved[str(row.get("id") if isinstance(row,dict) else None)]="malformed description row"
                            continue
                        if not args.category or row["category"] in args.category:
                            candidates.append((root,pack,row))
                prior = read(catalog)["assets"]
                if args.supply_only:
                    prior += state.get("test_candidates",[])
                known = {r["id"] for r in prior}
                hashes = {r["sha256"] for r in prior}
                motifs = {r.get("motif_key") for r in prior}
                prepared=[]
                for root,pack,row in candidates:
                    stats["candidates"]+=1
                    try:
                        path = inside(root,row["file_path"])
                        digest = sha(path)
                        if row["id"] in known or digest in hashes or row.get("motif_key") in motifs:
                            stats["duplicate"]+=1
                            continue
                        digest=validate(root,row,pack,args.supply_only,approved_map)
                    except (ValueError,KeyError,StopIteration,ET.ParseError,OSError) as error:
                        stats["review_or_invalid"]+=1
                        unresolved[row["id"]]=f"{type(error).__name__}: {error}"
                        continue
                    stats["validated"]+=1
                    known.add(row["id"])
                    hashes.add(digest)
                    motifs.add(row["motif_key"])
                    row["sha256"]=digest
                    prepared.append((root,pack,row))
                write(stage/"prior.json",prior)
                write(stage/"candidates.json",[row for _,_,row in prepared])
                subprocess.run([sys.executable,str(tools/"audit.py"),str(baseline),
                                str(stage/"candidates.json"),"--accepted",str(stage/"prior.json"),
                                "--out",str(stage/"audit.json")],env=env,check=True)
                checked=read(stage/"audit.json")["results"]
                accepted=[]
                for (root,pack,row),review in zip(prepared,checked,strict=True):
                    if review["status"]!="pending_review":
                        stats["duplicate"]+=1
                    elif row["id"] not in name_cleared and any(
                            review[k]["content"] for k in ("baseline","accepted_additions","earlier_candidates")):
                        stats["review_or_invalid"]+=1
                        unresolved[row["id"]]="name collision: "+", ".join(sorted(
                            {h for k in ("baseline","accepted_additions","earlier_candidates") for h in review[k]["content"]}))
                    else:
                        accepted.append((root,pack,row))
                        by_category[row["category"]]+=1
                state.update(stats=dict(stats),eligible_by_category=dict(by_category))
                review_log[source_id]=unresolved
                state["review_ids"]=sorted({i for reasons in review_log.values() for i in reasons})
                if args.supply_only:
                    state.setdefault("test_candidates",[]).extend(row for _,_,row in accepted)
                    state["completed"] += len(accepted)
                    accepted=[]
                while accepted and state["completed"]<args.target:
                    category=accepted[0][2]["category"]
                    policy=limits.get(category,{})
                    capacity=policy.get("target",args.target)-state["published_by_category"].get(category,0)
                    if capacity<=0:
                        accepted=[item for item in accepted if item[2]["category"]!=category]
                        continue
                    category_batch=policy.get("batch_size",args.batch_size)
                    if not isinstance(category_batch,int) or not 1<=category_batch<=50:
                        raise ValueError("Category batch size must be 1–50")
                    selected=[item for item in accepted if item[2]["category"]==category][:min(
                        category_batch,capacity,args.target-state["completed"])]
                    batch=read(progress)["next_batch"]
                    payload=stage/"payload"
                    payload.mkdir()
                    rows=[]
                    for i,(root,pack,row) in enumerate(selected):
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
                    state["pending"]=dict(base=base,batch=batch,count=len(rows),message=message,
                                          by_category=dict(Counter(r["category"] for r in rows)))
                    save()
                    shutil.move(str(payload),destination)
                    subprocess.run([sys.executable,str(tools/"finalize.py"),str(target),batch,str(baseline)],
                                   env=env,check=True)
                    git("add","--",str(destination),str(catalog),str(progress))
                    git("diff","--cached","--check")
                    git("-c","commit.gpgsign=false","commit","-m",message)
                    recover()
                    published={item[2]["id"] for item in selected}
                    accepted=[item for item in accepted if item[2]["id"] not in published]
                leftover=len(accepted)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
            if state["pending"]:
                raise
            history[source_id]={"status":"failed","error":str(error)}
            save()
            continue
        history[source_id]={"status":"complete" if not unresolved and not leftover else "partial",
                            "candidates":len(candidates),"unresolved":len(unresolved),"deferred":leftover}
        save()
    state["result"]="target_reached" if state["completed"]>=args.target else "candidate_pool_exhausted"
    state["category_shortfall"]={category:max(0,policy["target"]-state["published_by_category"].get(category,0))
                                 for category,policy in limits.items() if "target" in policy}
    state["shortfall"]=max(0,args.target-state["completed"])
    save()
    print(json.dumps(state,ensure_ascii=False,indent=2))
    lock.close()
    if state["shortfall"] and not args.supply_only:
        # Exit 3 = ran cleanly but the approved pool could not reach the target.
        sys.exit(3)


if __name__=="__main__":
    main()
