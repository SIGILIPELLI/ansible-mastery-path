"""Tests for the webapp role using the real ansible-playbook and ansible-lint (skipped if not installed)."""
import os, re, shutil, subprocess, sys
from pathlib import Path
import pytest
BIN = Path(sys.executable).parent
HERE = Path(__file__).parent
pytestmark = pytest.mark.skipif(not (BIN / "ansible-playbook").exists(), reason="ansible not installed")
ENV = {**os.environ, "ANSIBLE_NOCOLOR": "1", "ANSIBLE_LOCALHOST_WARNING": "False", "ANSIBLE_INVENTORY_UNPARSED_WARNING": "False", "ANSIBLE_HOME": str(HERE / ".ansible_home"), "ANSIBLE_ROLES_PATH": str(HERE / "roles")}

def play(tmp, extra=(), vars_=None):
    inv = tmp / "inv.ini"
    inv.write_text(f"[web]\nw1 ansible_connection=local\nw2 ansible_connection=local webapp_port=9000\n[all:vars]\nansible_python_interpreter={sys.executable}\nwebapp_root={tmp}/out/{{{{ inventory_hostname }}}}\n")
    pb = tmp / "site.yml"; pb.write_text("- hosts: web\n  gather_facts: false\n  roles:\n    - role: webapp\n" + (f"      vars: {vars_}\n" if vars_ else ""))
    p = subprocess.run([str(BIN / "ansible-playbook"), "-i", str(inv), str(pb), *extra], capture_output=True, text=True, env=ENV, cwd=tmp)
    recap = {m[1]: {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", m[2])} for m in re.finditer(r"^(\w+)\s+:(.*)$", p.stdout, re.M)}
    return p.returncode, recap, p.stdout + p.stderr

def test_defaults_and_per_host_override(tmp_path):
    rc, recap, _ = play(tmp_path); assert rc == 0
    assert "port=8080" in (tmp_path / "out/w1/webapp.conf").read_text() and "port=9000" in (tmp_path / "out/w2/webapp.conf").read_text()
def test_role_param_overrides_default(tmp_path):
    play(tmp_path, vars_="{webapp_workers: 7}"); assert "workers=7" in (tmp_path / "out/w1/webapp.conf").read_text()
def test_idempotent(tmp_path):
    play(tmp_path); rc, recap, _ = play(tmp_path); assert rc == 0 and all(r["changed"] == 0 for r in recap.values())
def test_handler_fires_only_on_change(tmp_path):
    _, _, out1 = play(tmp_path); _, _, out2 = play(tmp_path)
    assert out1.count("RUNNING HANDLER") == 1 and out2.count("RUNNING HANDLER") == 0
def test_invalid_port_fails_before_changing_anything(tmp_path):
    rc, recap, out = play(tmp_path, vars_="{webapp_port: 70000}"); assert rc != 0 and "webapp_port must be" in out and not (tmp_path / "out").exists()
def test_zero_workers_rejected(tmp_path):
    rc, _, out = play(tmp_path, vars_="{webapp_workers: 0}"); assert rc != 0
def test_check_mode_writes_nothing(tmp_path):
    rc, recap, _ = play(tmp_path, extra=["--check"]); assert rc == 0 and not (tmp_path / "out").exists()
def test_role_param_beats_role_vars_file(tmp_path):
    # measured on ansible-core 2.21.5: a role parameter (higher precedence) overrides roles/webapp/vars/main.yml, so "internal constants" there are NOT protected
    play(tmp_path, vars_="{webapp_config_mode: '0600'}")
    assert oct((tmp_path / "out/w1/webapp.conf").stat().st_mode & 0o777) == "0o600"
def test_ansible_lint_production_profile_passes():
    if not (BIN / "ansible-lint").exists(): pytest.skip("ansible-lint not installed")
    p = subprocess.run([str(BIN / "ansible-lint"), "roles/webapp"], capture_output=True, text=True, cwd=HERE, env=ENV)
    assert p.returncode == 0, p.stdout + p.stderr
