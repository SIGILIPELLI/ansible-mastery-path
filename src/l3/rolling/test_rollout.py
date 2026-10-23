"""Rolling-update tests using the real ansible-playbook over 8 simulated servers (directories)."""
import json, os, re, subprocess, sys
from pathlib import Path
import pytest
HERE = Path(__file__).parent; BIN = Path(sys.executable).parent
pytestmark = pytest.mark.skipif(not (BIN / "ansible-playbook").exists(), reason="ansible not installed")
HOSTS = [f"n{i}" for i in range(1, 9)]
ENV = {**os.environ, "ANSIBLE_NOCOLOR": "1", "ANSIBLE_LOCALHOST_WARNING": "False", "ANSIBLE_HOME": str(HERE / ".ansible_home")}

def setup(sb):
    for h in HOSTS:
        d = sb / h; d.mkdir(parents=True); (d / "version").write_text("1.0\n"); (d / "in_rotation").touch()

def run(sb, **extra):
    inv = sb.parent / "inv.ini"; inv.write_text((HERE / "inventory.ini").read_text().replace("/private/tmp/claude-501/ans/bin/python", sys.executable))
    ev = {"sandbox": str(sb), **extra}
    p = subprocess.run([str(BIN / "ansible-playbook"), "-i", str(inv), str(HERE / "rollout.yml"), "-e", json.dumps(ev)], capture_output=True, text=True, env=ENV, cwd=HERE)
    return p.returncode, p.stdout

def versions(sb): return {h: (sb / h / "version").read_text().strip() for h in HOSTS}
def in_rot(sb): return {h for h in HOSTS if (sb / h / "in_rotation").exists()}
def play_headers(out): return len(re.findall(r"^PLAY \[Rolling update\]", out, re.M))

def test_happy_path_updates_everyone_in_three_batches(tmp_path):
    sb = tmp_path / "sb"; setup(sb); rc, out = run(sb)
    assert rc == 0 and set(versions(sb).values()) == {"2.0"} and in_rot(sb) == set(HOSTS) and play_headers(out) == 3
def test_batch_sizes_are_1_then_half_then_rest(tmp_path):
    sb = tmp_path / "sb"; setup(sb); _, out = run(sb)
    batches = [re.findall(r"^TASK \[Drain[^\n]*\n((?:changed|ok): \[n\d\][^\n]*\n)+", chunk, re.M) for chunk in out.split("PLAY [Rolling update]")[1:]]
    sizes = [len(re.findall(r"\[(n\d)\]", chunk.split("TASK [Log drain]")[0])) for chunk in out.split("PLAY [Rolling update]")[1:]]
    assert sizes == [1, 4, 3]       # 1, then 50% of 8 = 4, then the remaining 3
def test_canary_failure_stops_rollout_and_rolls_back_only_the_canary(tmp_path):
    sb = tmp_path / "sb"; setup(sb); rc, out = run(sb, bad_hosts=["n1"])
    assert rc != 0 and versions(sb)["n1"] == "1.0" and all(v == "1.0" for v in versions(sb).values()) and in_rot(sb) == set(HOSTS) and play_headers(out) == 1
    assert (sb / "n1" / "events.log").read_text().splitlines() == ["drained", "rolled back"]
def test_failure_in_second_batch_keeps_first_batch_updated_and_stops(tmp_path):
    sb = tmp_path / "sb"; setup(sb); rc, out = run(sb, bad_hosts=["n3"])
    v = versions(sb)
    assert rc != 0 and v["n1"] == "2.0" and v["n3"] == "1.0" and v["n6"] == "1.0" and v["n8"] == "1.0"          # batches: [n1] [n2..n5] [n6..n8]
    assert in_rot(sb) == set(HOSTS)                                                                               # nobody left drained
def test_nodes_in_failed_batch_after_the_failure_point_may_be_updated(tmp_path):
    sb = tmp_path / "sb"; setup(sb); run(sb, bad_hosts=["n3"])
    assert {versions(sb)[h] for h in ("n2", "n4", "n5")} <= {"1.0", "2.0"}      # others in the same batch ran independently; we only assert they are consistent
def test_rerun_after_fix_finishes_the_job(tmp_path):
    sb = tmp_path / "sb"; setup(sb); run(sb, bad_hosts=["n3"]); rc, _ = run(sb)
    assert rc == 0 and set(versions(sb).values()) == {"2.0"}
def test_idempotent_second_run_changes_nothing_in_versions(tmp_path):
    sb = tmp_path / "sb"; setup(sb); run(sb); before = versions(sb); run(sb); assert versions(sb) == before

@pytest.mark.parametrize("mode,expected", [("plain", 5), ("always_only", 8), ("rescue_always", 8), ("anyfatal", 5)])
def test_which_batches_start_after_a_failure_in_batch_two(tmp_path, mode, expected):
    """Pins measured ansible-core 2.21.5 behaviour: with max_fail_percentage 0, a failed block WITH an `always:` section did not stop batch 3 (8 hosts started);
    without `always:` it did (5). any_errors_fatal stops in every shape. If a future version fixes this, the test fails and the lesson needs updating."""
    inv = tmp_path / "inv.ini"; inv.write_text((HERE / "inventory.ini").read_text().replace("/private/tmp/claude-501/ans/bin/python", sys.executable))
    p = subprocess.run([str(BIN / "ansible-playbook"), "-i", str(inv), str(HERE / "abort_semantics.yml"), "-e", f"mode={mode}"], capture_output=True, text=True, env=ENV, cwd=HERE)
    assert len(set(re.findall(r"start on (n\d)", p.stdout))) == expected
