from pathlib import Path
import hashlib

def file_manifest(raw_dir: Path):
    rows=[]
    for p in sorted(raw_dir.iterdir()):
        if p.is_file():
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            rows.append({"file":p.name,"size":p.stat().st_size,"sha256":h})
    return rows
