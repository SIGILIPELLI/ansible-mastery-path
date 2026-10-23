"""Capstone: operate a simulated 12-node fleet end to end with the course's tools (real ansible-playbook, driftaudit, preflight, nologlint)."""
import os, re, subprocess, sys, time
from pathlib import Path
import pytest
HERE = Path(__file__).parent; L4 = HERE.parent; BASE = L4.parent / "baseline"; BIN = Path(sys.executable).parent
sys.path.insert(0, str(L4 / "audit")); sys.path.insert(0, str(L4)); sys.path.insert(0, str(HERE))
pytestmark = pytest.mark.skipif(not (BIN / "ansible-playbook").exists(), reason="ansible not installed")
import driftaudit, fleet, nologlint

PLAYBOOK = BASE / "baseline_ci.yml"
ENV = {**os.environ, "ANSIBLE_NOCOLOR": "1", "ANSIBLE_LOCALHOST_WARNING": "False", "ANSIBLE_INVENTORY_UNPARSED_WARNING": "False"}

@pytest.fixture(scope="module")
def fleet_env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fleet"); inv = tmp / "hosts.ini"; inv.write_text(fleet.inventory_text()); sb = tmp / "sb"
    env = {**ENV, "ANSIBLE_HOME": str(tmp / "home")}
    return {"tmp": tmp, "inv": inv, "sb": sb, "env": env}

def apply(fe, *extra):
    p = subprocess.run([str(BIN / "ansible-playbook"), "-i", str(fe["inv"]), str(PLAYBOOK), "-e", f"sandbox={fe['sb']}", *extra], capture_output=True, text=True, env=fe["env"], cwd=BASE)
    recap = {m[1]: dict((k, int(v)) for k, v in re.findall(r"(\w+)=(\d+)", m[2])) for m in re.finditer(r"^(\w+)\s+:(.*)$", p.stdout, re.M)}
    return p.returncode, recap

def test_01_playbook_is_clean_for_secret_hygiene(): assert nologlint.lint_text(PLAYBOOK.read_text()) == []
def test_02_playbook_passes_ansible_lint(fleet_env):
    if not (BIN / "ansible-lint").exists(): pytest.skip("ansible-lint not installed")
    p = subprocess.run([str(BIN / "ansible-lint"), str(PLAYBOOK)], capture_output=True, text=True, env=fleet_env["env"], cwd=BASE); assert p.returncode == 0, p.stdout[-800:]
def test_03_first_converge_changes_all_12_nodes(fleet_env):
    rc, recap = apply(fleet_env); assert rc == 0 and len(recap) == 12 and all(r["changed"] == 6 and r["failed"] == 0 for r in recap.values())
def test_04_second_run_is_idempotent(fleet_env):
    rc, recap = apply(fleet_env); assert rc == 0 and all(r["changed"] == 0 for r in recap.values())
def test_05_audit_finds_exactly_the_drifted_nodes_and_repairs_nothing(fleet_env):
    sb = fleet_env["sb"]
    (sb / "web03/etc/app/app.conf").write_text("port = 1\n")           # content drift
    (sb / "db02/var/lib/app").chmod(0o777)                              # permission drift
    (sb / "web07/etc/motd").unlink()                                    # deleted file
    before = {p: p.read_bytes() for p in [sb / "web03/etc/app/app.conf", sb / "web07/etc"/ "sshd_config"]}
    rep, st = driftaudit.run_audit(PLAYBOOK, fleet_env["inv"], ["-e", f"sandbox={sb}"])
    assert st == 1 and rep["drifted_hosts"] == ["db02", "web03", "web07"]
    assert (sb / "web03/etc/app/app.conf").read_text() == "port = 1\n" and not (sb / "web07/etc/motd").exists()      # audit changed nothing
def test_06_preflight_blocks_fleet_wide_and_production_runs(fleet_env):
    def run(*a): return subprocess.run([sys.executable, str(L4 / "preflight.py"), str(fleet_env["inv"]), *a], capture_output=True, text=True)
    r = run("all", "--max-hosts", "5", "--allow-protected"); assert r.returncode == 1 and "exceeds" in r.stdout
    r = run("web03"); assert r.returncode == 1 and "production" in r.stdout
    assert run("web03,db02,web07", "--max-hosts", "5", "--allow-protected").returncode == 0
def test_07_targeted_repair_touches_only_the_drifted_nodes(fleet_env):
    sb = fleet_env["sb"]; untouched = [sb / n / "etc/app/app.conf" for n in ("web01", "web02", "db01", "db04")]
    stamps = {p: p.stat().st_mtime_ns for p in untouched}; time.sleep(0.05)
    rc, recap = apply(fleet_env, "--limit", "web03,db02,web07")
    assert rc == 0 and set(recap) == {"web03", "db02", "web07"} and all(r["changed"] >= 1 for r in recap.values())
    assert {p: p.stat().st_mtime_ns for p in untouched} == stamps
def test_08_audit_is_clean_after_repair(fleet_env):
    rep, st = driftaudit.run_audit(PLAYBOOK, fleet_env["inv"], ["-e", f"sandbox={fleet_env['sb']}"]); assert st == 0 and rep["drifted_hosts"] == []
def test_09_per_node_variables_survived(fleet_env):
    sb = fleet_env["sb"]; assert "port = 8003" in (sb / "web03/etc/app/app.conf").read_text() and "port = 5402" in (sb / "db02/etc/app/app.conf").read_text()
