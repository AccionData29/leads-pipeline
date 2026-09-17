from pathlib import Path
import json

def write_report(output_dir: Path, run_id, metrics, counts):
    output_dir.mkdir(parents=True,exist_ok=True)
    report={"run_id":run_id,"metrics":metrics,"counts":counts}
    (output_dir/f"run_{run_id}.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
