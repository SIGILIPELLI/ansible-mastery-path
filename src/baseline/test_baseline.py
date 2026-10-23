"""Runs the REAL ansible-playbook against the baseline (local connection, sandbox under tmp_path). Needs ansible-core installed; skips otherwise."""
import os, re, shutil, stat, subprocess, sys
from pathlib import Path
import pytest
ANS = shutil.which("ansible-playbook") or str(Path(sys.executable).parent / "ansible-playbook")
pytestmark = pytest.mark.skipif(not Path(ANS).exists(), reason="ansible-playbook not installed")
HERE = Path(__file__).parent
ENV = {**os.environ, "ANSIBLE_NOCOLOR": "1", "ANSIBLE_LOCALHOST_WARNING": "False", "ANSIBLE_INVENTORY_UNPARSED_WARNING": "False", "ANSIBLE_HOME": str(HERE / ".ansible_home")}

def run(sandbox, *extra):
    inv = HERE / "inventory.ini"
    py = str(Path(sys.executable))
    text = inv.read_text().replace("/private/tmp/claude-501/ans/bin/python", py)
    tmp_inv = Path(sandbox).parent / "inv.ini"; tmp_inv.write_text(text)
    p = subprocess.run([ANS, "-i", str(tmp_inv), str(HERE / "baseline.yml"), "-e", f"sandbox={sandbox}", *extra], capture_output=True, text=True, env=ENV, cwd=HERE)
    recap = {m[1]: dict(re.findall(r"(\w+)=(\d+)", m[2])) for m in re.finditer(r"^(node\d)\s+:(.*)$", p.stdout, re.M)}
    return p.returncode, {h: {k: int(v) for k, v in d.items()} for h, d in recap.items()}, p.stdout

@pytest.fixture
def sb(tmp_path): return str(tmp_path / "sandbox")

def test_first_run_changes_everything(sb):
    rc, recap, _ = run(sb); assert rc == 0 and recap["node1"]["changed"] == 6 and recap["node2"]["changed"] == 6
def test_second_run_is_idempotent(sb):
    run(sb); rc, recap, _ = run(sb); assert rc == 0 and all(r["changed"] == 0 and r["failed"] == 0 for r in recap.values())
def test_check_mode_makes_no_changes_to_disk(sb):
    rc, recap, _ = run(sb, "--check"); assert rc == 0 and recap["node1"]["changed"] >= 5 and not Path(sb).exists()
def test_per_host_variable_reaches_template(sb):
    run(sb); assert "port = 8080" in (Path(sb) / "node1/etc/app/app.conf").read_text() and "port = 9090" in (Path(sb) / "node2/etc/app/app.conf").read_text()
def test_modes_are_enforced(sb):
    run(sb); assert stat.S_IMODE((Path(sb) / "node1/var/lib/app").stat().st_mode) == 0o700 and stat.S_IMODE((Path(sb) / "node1/etc/sshd_config").stat().st_mode) == 0o600
def test_drift_is_detected_by_check_mode_and_repaired_by_run(sb):
    run(sb); conf = Path(sb) / "node1/etc/app/app.conf"; conf.write_text(conf.read_text() + "port = 1\n")
    rc, recap, out = run(sb, "--check", "--diff"); assert recap["node1"]["changed"] >= 1 and recap["node2"]["changed"] == 0 and "port = 1" in conf.read_text()
    run(sb); assert "port = 1" not in conf.read_text()
    assert run(sb)[1]["node1"]["changed"] == 0
def test_handler_runs_only_when_config_changes(sb):
    run(sb); counter = Path(sb) / "node1/var/lib/app/restart.count"; assert counter.read_text().strip() == "1"
    run(sb); assert counter.read_text().strip() == "1"                      # unchanged config: no restart
    run(sb, "-e", "workers=4"); assert counter.read_text().strip() == "2"    # changed config: one restart
def test_manual_edit_of_sshd_config_is_reverted(sb):
    run(sb); f = Path(sb) / "node1/etc/sshd_config"; f.write_text("PermitRootLogin yes\n"); run(sb); assert f.read_text().strip() == "PermitRootLogin no"
