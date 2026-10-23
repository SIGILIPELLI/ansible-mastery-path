import subprocess, sys
from pathlib import Path
import pytest
import preflight
BIN = Path(sys.executable).parent
def test_assess_ok(): assert preflight.assess(["a", "b"], {"a": ["web"], "b": ["web"]}, 5, {"production"}, False) == []
def test_assess_too_many(): assert "exceeds" in preflight.assess(list("abcdef"), {}, 5, set(), False)[0]
def test_assess_protected_blocked(): assert "protected" in preflight.assess(["a"], {"a": ["production"]}, 5, {"production"}, False)[0]
def test_assess_protected_allowed(): assert preflight.assess(["a"], {"a": ["production"]}, 5, {"production"}, True) == []
def test_assess_empty(): assert preflight.assess([], {}, 5, set(), False) == ["pattern matches no hosts"]
def test_groups_of_ignores_meta_and_includes_ancestors(): assert preflight.groups_of({"_meta": {}, "web": {"hosts": ["a"]}, "all": {"children": ["web"]}}, ["a"]) == {"a": ["all", "web"]}
def test_groups_of_multi_level(): assert preflight.groups_of({"leaf": {"hosts": ["h"]}, "mid": {"children": ["leaf"]}, "production": {"children": ["mid"]}}, ["h"]) == {"h": ["leaf", "mid", "production"]}
def test_groups_of_cycle_safe(): assert preflight.groups_of({"a": {"hosts": ["h"], "children": ["b"]}, "b": {"children": ["a"]}}, ["h"]) == {"h": ["a", "b"]}
@pytest.mark.skipif(not (BIN / "ansible").exists(), reason="ansible not installed")
def test_end_to_end(tmp_path):
    inv = tmp_path / "i.ini"; inv.write_text("[web]\nw1 ansible_connection=local\nw2 ansible_connection=local\n[production:children]\nweb\n")
    def run(*a): return subprocess.run([sys.executable, str(Path(preflight.__file__)), str(inv), *a], capture_output=True, text=True)
    assert run("w1", "--protected", "staging").returncode == 0
    r = run("w1"); assert r.returncode == 1 and "protected" in r.stdout
    assert run("w1", "--allow-protected").returncode == 0
    assert run("web", "--max-hosts", "1", "--allow-protected").returncode == 1
    assert run("nomatch", "--allow-protected").returncode == 1
