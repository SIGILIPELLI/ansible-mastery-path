"""Tests for the custom modules. Unit tests exercise the pure function; module tests run the module the way Ansible does (a JSON args file) and, last, through the real ansible-playbook."""
import hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "library"))
try:
    import kvfile, filehash                      # need ansible-core importable (module_utils)
except ImportError:
    pytest.skip("ansible-core not importable", allow_module_level=True)

def run_module(name, args, tmp_path, check=False):
    a = dict(args)
    if check: a["_ansible_check_mode"] = True
    a.setdefault("_ansible_diff", True)
    argfile = tmp_path / "args.json"; argfile.write_text(json.dumps({"ANSIBLE_MODULE_ARGS": a}))
    p = subprocess.run([sys.executable, str(HERE / "library" / f"{name}.py"), str(argfile)], capture_output=True, text=True)
    out = json.loads(p.stdout.strip().splitlines()[-1]); return p.returncode, out

# ---- pure function -------------------------------------------------------------
def test_apply_adds_missing_key(): assert kvfile.apply(["a=1"], "b", "2", "present")[0] == ["a=1", "b=2"]
def test_apply_replaces_value(): assert kvfile.apply(["a=1", "b=2"], "a", "9", "present") == (["a=9", "b=2"], "1", "9")
def test_apply_unchanged_returns_same_lines(): lines = ["a=1", "# c"]; assert kvfile.apply(lines, "a", "1", "present")[0] == lines
def test_apply_absent_removes(): assert kvfile.apply(["a=1", "b=2"], "a", None, "absent") == (["b=2"], "1", None)
def test_apply_absent_when_missing_is_noop(): assert kvfile.apply(["b=2"], "a", None, "absent")[0] == ["b=2"]
def test_apply_keeps_comments_and_blank_lines(): assert kvfile.apply(["# a=1", "", "x=1"], "a", "2", "present")[0] == ["# a=1", "", "x=1", "a=2"]
def test_apply_removes_duplicates(): assert kvfile.apply(["a=1", "a=2", "a=3"], "a", "5", "present")[0] == ["a=5"]
def test_apply_spaces_around_equals(): assert kvfile.apply(["a = 1"], "a", "1", "present")[0] == ["a=1"]
def test_apply_empty_file(): assert kvfile.apply([], "a", "1", "present")[0] == ["a=1"]
def test_apply_key_prefix_not_confused(): assert kvfile.apply(["ab=1"], "a", "2", "present")[0] == ["ab=1", "a=2"]
def test_hash_matches_hashlib(tmp_path):
    f = tmp_path / "x"; f.write_bytes(b"hello"); assert filehash.compute(str(f), "sha256")[0] == hashlib.sha256(b"hello").hexdigest()

# ---- module as Ansible runs it ---------------------------------------------------
def test_module_creates_changes_then_idempotent(tmp_path):
    f = tmp_path / "s.conf"
    rc, out = run_module("kvfile", {"path": str(f), "key": "w", "value": "4", "create": True}, tmp_path); assert rc == 0 and out["changed"] and f.read_text() == "w=4\n"
    rc, out = run_module("kvfile", {"path": str(f), "key": "w", "value": "4"}, tmp_path); assert rc == 0 and not out["changed"]
def test_module_check_mode_does_not_write(tmp_path):
    f = tmp_path / "s.conf"; f.write_text("w=1\n")
    rc, out = run_module("kvfile", {"path": str(f), "key": "w", "value": "2"}, tmp_path, check=True); assert out["changed"] and f.read_text() == "w=1\n"
def test_module_reports_diff(tmp_path):
    f = tmp_path / "s.conf"; f.write_text("w=1\n")
    _, out = run_module("kvfile", {"path": str(f), "key": "w", "value": "2"}, tmp_path); assert out["diff"]["before"] == "w=1\n" and out["diff"]["after"] == "w=2\n"
def test_module_sets_mode(tmp_path):
    f = tmp_path / "s.conf"; f.write_text("w=1\n")
    run_module("kvfile", {"path": str(f), "key": "w", "value": "2", "mode": "0640"}, tmp_path); assert oct(f.stat().st_mode & 0o777) == "0o640"
def test_module_mode_only_change_is_reported(tmp_path):
    f = tmp_path / "s.conf"; f.write_text("w=1\n"); f.chmod(0o600)
    _, out = run_module("kvfile", {"path": str(f), "key": "w", "value": "1", "mode": "0644"}, tmp_path); assert out["changed"] and oct(f.stat().st_mode & 0o777) == "0o644"
@pytest.mark.parametrize("args,msg", [({"key": "bad key", "value": "x"}, "invalid key"), ({"key": "k"}, "missing"), ({"key": "k", "value": "a\nb"}, "newlines")])
def test_module_rejects_bad_input(tmp_path, args, msg):
    f = tmp_path / "s.conf"; f.write_text("")
    rc, out = run_module("kvfile", {"path": str(f), **args}, tmp_path); assert rc != 0 and out["failed"] and msg in out["msg"]
def test_module_missing_file_without_create_fails(tmp_path):
    rc, out = run_module("kvfile", {"path": str(tmp_path / "no"), "key": "k", "value": "v"}, tmp_path); assert out["failed"]
def test_module_absent_on_missing_file_is_noop(tmp_path):
    rc, out = run_module("kvfile", {"path": str(tmp_path / "no"), "key": "k", "state": "absent"}, tmp_path); assert rc == 0 and not out["changed"]
def test_unknown_argument_rejected(tmp_path):
    f = tmp_path / "s.conf"; f.write_text("")
    rc, out = run_module("kvfile", {"path": str(f), "key": "k", "value": "v", "valeu": "typo"}, tmp_path); assert out["failed"] and "Unsupported parameters" in out["msg"]
def test_filehash_missing_file(tmp_path):
    rc, out = run_module("filehash", {"path": str(tmp_path / "no")}, tmp_path); assert out["failed"] and "not found" in out["msg"]
def test_filehash_output(tmp_path):
    f = tmp_path / "x"; f.write_bytes(b"abc"); _, out = run_module("filehash", {"path": str(f)}, tmp_path); assert out["digest"] == hashlib.sha256(b"abc").hexdigest() and out["size"] == 3 and not out["changed"]

# ---- through the real ansible-playbook -----------------------------------------------
@pytest.mark.skipif(not (Path(sys.executable).parent / "ansible-playbook").exists(), reason="ansible-playbook not installed")
def test_in_playbook_second_run_unchanged(tmp_path):
    inv = tmp_path / "inv.ini"; inv.write_text(f"localhost ansible_connection=local ansible_python_interpreter={sys.executable}\n")
    pb = tmp_path / "p.yml"; pb.write_text(f"- hosts: localhost\n  gather_facts: false\n  tasks:\n    - kvfile: {{path: {tmp_path}/c.conf, key: a, value: '1', create: true}}\n")
    env = {**os.environ, "ANSIBLE_LIBRARY": str(HERE / "library"), "ANSIBLE_NOCOLOR": "1", "ANSIBLE_HOME": str(tmp_path / "home")}
    def go(): return subprocess.run([str(Path(sys.executable).parent / "ansible-playbook"), "-i", str(inv), str(pb)], capture_output=True, text=True, env=env).stdout
    assert "changed=1" in go() and "changed=0" in go()
