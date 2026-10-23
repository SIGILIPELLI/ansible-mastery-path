#!/usr/bin/env python3
"""driftaudit: run a playbook in check+diff mode with the driftreport callback and summarise drift.
Exit status: 0 = no drift, 1 = drift found, 2 = a task failed or a host was unreachable (the audit itself is untrustworthy)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGINS = HERE.parent / "callback_plugins"

def run_audit(playbook, inventory, extra=(), ansible_bin=None):
    ansible_bin = ansible_bin or str(Path(sys.executable).parent / "ansible-playbook")
    with tempfile.TemporaryDirectory() as tmp:
        report_file = Path(tmp) / "report.json"
        env = {**os.environ, "ANSIBLE_CALLBACK_PLUGINS": str(PLUGINS), "ANSIBLE_CALLBACKS_ENABLED": "driftreport", "DRIFT_REPORT_FILE": str(report_file),
               "ANSIBLE_NOCOLOR": "1", "ANSIBLE_LOCALHOST_WARNING": "False", "ANSIBLE_INVENTORY_UNPARSED_WARNING": "False", "ANSIBLE_HOME": str(Path(tmp) / "home")}
        p = subprocess.run([ansible_bin, "-i", str(inventory), str(playbook), "--check", "--diff", *extra], capture_output=True, text=True, env=env)
        if not report_file.exists():
            return {"error": "no report produced", "returncode": p.returncode, "stderr": p.stderr[-500:]}, 2
        report = json.loads(report_file.read_text())
    report["returncode"] = p.returncode
    status = 2 if report["failed_hosts"] else (1 if report["drifted_hosts"] else 0)
    return report, status

def summarize(report):
    if "error" in report: return f"AUDIT ERROR: {report['error']}"
    lines = [f"hosts audited: {len(report['hosts'])}  drifted: {len(report['drifted_hosts'])}  failed: {len(report['failed_hosts'])}"]
    by_host = {}
    for f in report["findings"]:
        by_host.setdefault(f["host"], []).append(f)
    for host, items in sorted(by_host.items()):
        lines.append(f"- {host}")
        for f in items:
            extra = f" items={f['items']}" if f.get("items") else ""
            lines.append(f"    [{f['kind']}] {f['task']}{extra}")
    return "\n".join(lines)

def main(argv):
    if len(argv) < 2:
        print("usage: driftaudit.py playbook inventory [ansible args...]", file=sys.stderr); return 2
    report, status = run_audit(argv[0], argv[1], argv[2:])
    print(summarize(report)); return status

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
