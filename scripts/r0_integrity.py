"""Archive exact R0 evidence and verify serial/parallel equivalence (stdlib)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import time


def hashes(root):
    root = Path(root)
    return {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and
            p.name not in ("SHA256SUMS", "archive.log", "integrity.json") and not p.name.endswith(".tmp")}


def scientific(row):
    out = dict(row)
    out.pop("wall_s", None)
    return out


def compare(left, right):
    def records(root):
        return {p.name: scientific(json.loads(p.read_text(encoding="utf-8"))) for p in (Path(root)/"units").glob("*.json")}
    a, b = records(left), records(right)
    if not a or a.keys() != b.keys() or a != b:
        raise ValueError("serial/parallel scientific records differ or are incomplete")
    return {"exact": True, "units": len(a), "ignored": ["wall_s"]}


def archive(root):
    root = Path(root).resolve()
    if not root.is_dir() or root == root.parent:
        raise ValueError("invalid evidence root")
    hs = hashes(root)
    (root/"SHA256SUMS").write_text("".join(f"{h}  {n}\n" for n,h in hs.items()), encoding="utf-8", newline="\n")
    target = root.parent/(root.name+f"_{time.time_ns()}.tgz")
    if target.exists():
        raise ValueError("refusing to replace an existing archive")
    with tarfile.open(target, "w:gz") as t:
        t.add(root, arcname=root.name)
    with tarfile.open(target, "r:gz") as t:
        for name, expected in hs.items():
            if hashlib.sha256(t.extractfile(root.name+"/"+name).read()).hexdigest() != expected:
                raise ValueError("archive verification failed")
    return {"archive": str(target), "bytes": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "files_verified": len(hs)}


def main():
    p=argparse.ArgumentParser(__doc__)
    q=p.add_subparsers(dest="cmd", required=True)
    a=q.add_parser("archive");a.add_argument("--root",required=True)
    a=q.add_parser("compare");a.add_argument("--left",required=True);a.add_argument("--right",required=True)
    a=q.add_parser("audit");a.add_argument("--root",required=True);a.add_argument("--study",required=True)
    a=p.parse_args()
    if a.cmd=="compare":
        result=compare(a.left,a.right)
    elif a.cmd=="archive":
        result=archive(a.root)
    else:
        import r0_experiment as r0
        p,cases=r0.load_study(a.study)
        jobs=r0.units(p,cases)
        provenance=r0.read(Path(a.root)/"execution.json")
        r0.validate_provenance(provenance,a.study)
        paths=list((Path(a.root)/"units").glob("*.json"))
        expected={r0.unit_id(j):j for j in jobs}
        if {f.stem for f in paths}!=set(expected):
            raise ValueError("incomplete or extra evidence")
        for f in paths:
            r0.validate_record(r0.read(f),expected[f.stem],provenance)
        result={"complete":True,"units":len(paths),"hashes":hashes(a.root)}
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
