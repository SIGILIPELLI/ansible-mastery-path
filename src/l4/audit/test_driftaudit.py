import shutil, subprocess, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent))
import driftaudit
HERE = Path(__file__).parent; BASE = HERE.parent.parent / "baseline"
pytestmark = pytest.mark.skipif(not (Path(sys.executable).parent / "ansible-playbook").exists(), reason="ansible not installed")

def inv(tmp):
    p = tmp / "inv.ini"; p.write_text((BASE / "inventory.ini").read_text().replace("/private/tmp/claude-501/ans/bin/python", sys.executable)); return p

def converge(tmp, sb):
    env = {"ANSIBLE_NOCOLOR": "1", "ANSIBLE_HOME": str(tmp / "h"), "PATH": "/usr/bin:/bin"}
    subprocess.run([str(Path(sys.executable).parent / "ansible-playbook"), "-i", str(inv(tmp)), str(BASE / "baseline.yml"), "-e", f"sandbox={sb}"], check=True, capture_output=True, env=env)

def test_clean_fleet_exits_0(tmp_path):
    sb = tmp_path / "sb"; converge(tmp_path, sb); rep, st = driftaudit.run_audit(BASE / "baseline.yml", inv(tmp_path), ["-e", f"sandbox={sb}"])
    assert st == 0 and rep["drifted_hosts"] == [] and rep["check_mode"] is True
def test_drift_is_found_per_host_and_exit_1(tmp_path):
    sb = tmp_path / "sb"; converge(tmp_path, sb); (sb / "node2/etc/app/app.conf").write_text("port = 1\n")
    rep, st = driftaudit.run_audit(BASE / "baseline.yml", inv(tmp_path), ["-e", f"sandbox={sb}"])
    assert st == 1 and rep["drifted_hosts"] == ["node2"] and any(f["task"] == "app configuration" for f in rep["findings"])
def test_audit_does_not_repair(tmp_path):
    sb = tmp_path / "sb"; converge(tmp_path, sb); f = sb / "node1/etc/motd"; f.write_text("hand edit\n")
    driftaudit.run_audit(BASE / "baseline.yml", inv(tmp_path), ["-e", f"sandbox={sb}"]); assert f.read_text() == "hand edit\n"
def test_diff_content_is_captured(tmp_path):
    sb = tmp_path / "sb"; converge(tmp_path, sb); (sb / "node1/etc/sshd_config").write_text("PermitRootLogin yes\n")
    rep, _ = driftaudit.run_audit(BASE / "baseline.yml", inv(tmp_path), ["-e", f"sandbox={sb}"])
    text = str(rep["findings"]); assert "PermitRootLogin yes" in text and "PermitRootLogin no" in text
def test_looped_task_reports_which_items_drifted(tmp_path):
    sb = tmp_path / "sb"; converge(tmp_path, sb); (sb / "node1/var/lib/app").chmod(0o777)
    rep, _ = driftaudit.run_audit(BASE / "baseline.yml", inv(tmp_path), ["-e", f"sandbox={sb}"])
    assert any(f.get("items") == ["var/lib/app"] for f in rep["findings"])
def test_failure_makes_audit_untrustworthy_exit_2(tmp_path):
    pb = tmp_path / "bad.yml"; pb.write_text("- hosts: all\n  gather_facts: false\n  tasks:\n    - ansible.builtin.debug: {msg: '{{ nope }}'}\n")
    rep, st = driftaudit.run_audit(pb, inv(tmp_path)); assert st == 2 and rep["failed_hosts"]
def test_first_run_on_empty_machine_is_all_drift(tmp_path):
    rep, st = driftaudit.run_audit(BASE / "baseline.yml", inv(tmp_path), ["-e", f"sandbox={tmp_path / 'new'}"]); assert st == 1 and set(rep["drifted_hosts"]) == {"node1", "node2"}
def test_summarize_is_readable():
    rep = {"hosts": {"a": {}}, "drifted_hosts": ["a"], "failed_hosts": [], "findings": [{"host": "a", "task": "t", "kind": "changed", "items": ["x"]}]}
    out = driftaudit.summarize(rep); assert "drifted: 1" in out and "[changed] t items=['x']" in out
def test_summarize_error():
    assert driftaudit.summarize({"error": "boom"}).startswith("AUDIT ERROR")
