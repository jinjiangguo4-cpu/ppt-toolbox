"""Integration fixture: synthetic SVGs verify transport, never production quality."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

controller = Path(__file__).with_name("run_knowledge_base_batch.py").resolve()
source, baseline = map(lambda p:Path(p).resolve(),sys.argv[1:])
with tempfile.TemporaryDirectory(prefix="ppt-integration-") as directory:
    root=Path(directory)
    repo=root/"checkout"
    remote=root/"remote.git"
    def run(*args,cwd=root,**kwargs):
        return subprocess.run(args,cwd=cwd,check=True,**kwargs)
    run("git","init","--bare",str(remote))
    run("git","clone","--no-hardlinks",str(source),str(repo))
    run("git","remote","set-url","origin",str(remote),cwd=repo)
    run("git","config","user.name","Integration test",cwd=repo)
    run("git","config","user.email","integration@example.invalid",cwd=repo)
    run("git","push","origin","main",cwd=repo)
    pack=root/"fixtures"
    pack.mkdir()
    assets=[]
    approved={}
    for i in range(120):
        name=f"fixture-{i:03}"
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><rect width="{i+100}" height="540"/></svg>'
        path=pack/(name+".svg")
        path.write_text(svg,encoding="utf-8")
        approved[name]=hashlib.sha256(hashlib.sha256(path.read_bytes()).hexdigest().encode()).hexdigest()
        assets.append(dict(id=name,name_zh=name,name_en=name,category="材质背景",motif_key=name,
                           file_path=path.name,license="CC0-1.0"))
    assets.extend([dict(assets[0],id="repeat-fixture"),dict(assets[1],id="unapproved-fixture",
                 motif_key="unapproved-fixture",file_path="unapproved.svg")])
    (pack/"unapproved.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle r="3"/></svg>')
    (pack/"资源描述.json").write_text(json.dumps(assets,ensure_ascii=False),encoding="utf-8")
    plan=root/"plan.json"
    plan.write_text(json.dumps({"packs":[dict(directory="fixtures",original_cc0=True,approved=approved)]}))
    state=root/"state.json"
    cmd=[sys.executable,str(controller),"--repo",str(repo),"--baseline",str(baseline),
         "--plan",str(plan),"--state",str(state),"--target","1000","--batch-size","50"]
    # A pre-receive hook simulates an outage after the local commit.
    hook=remote/"hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    first=subprocess.run(cmd,cwd=root,capture_output=True)
    assert first.returncode!=0,first.stdout
    snapshot=json.loads(state.read_text(encoding="utf-8"))
    assert snapshot["pending"]["count"]==50 and snapshot["completed"]==0, first.stderr
    hook.unlink()
    run(*cmd)
    result=json.loads(state.read_text(encoding="utf-8"))
    assert result["completed"]==120 and result["shortfall"]==880
    assert [x["count"] for x in result["commits"]]==[50,50,20]
    assert result["stats"]["duplicate"]>=1 and result["stats"]["review_or_invalid"]>=1
    index=json.loads((repo/"新增资源/增量索引.json").read_text(encoding="utf-8"))["assets"]
    assert len(index)==231 and len({r["id"] for r in index})==231
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo)
    run(*cmd)
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo)==head
    print("PASS: 122 fixtures, 120 accepted, outage recovery, 3 pushes, 231 unique index records, idempotent replay")
