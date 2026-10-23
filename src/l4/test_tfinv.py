import json, subprocess, sys
from pathlib import Path
import pytest
import tfinv
HERE = Path(__file__).parent
OUT = {"web_ips": {"value": ["10.0.1.11", "10.0.1.12"], "type": ["tuple", ["string", "string"]], "sensitive": False}, "db_hosts": {"value": "10.0.2.5", "type": "string", "sensitive": False}, "other": {"value": 1, "type": "number", "sensitive": False}}
def test_groups_and_hosts():
    inv = tfinv.build(OUT); assert inv["web"]["hosts"] == ["web-01", "web-02"] and inv["db"]["hosts"] == ["db-01"] and inv["_meta"]["hostvars"]["web-02"]["ansible_host"] == "10.0.1.12"
def test_unknown_outputs_ignored(): assert "other" not in json.dumps(tfinv.build(OUT))
def test_sensitive_refused():
    with pytest.raises(ValueError, match="sensitive"): tfinv.build({"web_ips": {"value": ["1.1.1.1"], "sensitive": True}})
def test_no_known_outputs_is_an_error_not_an_empty_inventory():
    with pytest.raises(ValueError, match="no known outputs"): tfinv.build({"other": {"value": 1}})
def test_bad_address_rejected():
    with pytest.raises(ValueError, match="non-empty string"): tfinv.build({"web_ips": {"value": ["10.0.0.1", ""]}})
def test_cli_list_from_file(tmp_path):
    f = tmp_path / "o.json"; f.write_text(json.dumps(OUT)); p = subprocess.run([sys.executable, str(HERE / "tfinv.py"), "--list", str(f)], capture_output=True, text=True)
    assert p.returncode == 0 and json.loads(p.stdout)["web"]["hosts"] == ["web-01", "web-02"]
def test_cli_invalid_json_exits_1(tmp_path):
    f = tmp_path / "o.json"; f.write_text("not json"); p = subprocess.run([sys.executable, str(HERE / "tfinv.py"), "--list", str(f)], capture_output=True, text=True); assert p.returncode == 1 and "tfinv:" in p.stderr
def test_cli_usage_exit_2(): assert subprocess.run([sys.executable, str(HERE / "tfinv.py")], capture_output=True, text=True).returncode == 2
def test_host_flag_returns_empty_object(): assert subprocess.run([sys.executable, str(HERE / "tfinv.py"), "--host", "x"], capture_output=True, text=True).stdout.strip() == "{}"

def test_env_file_used_when_called_like_ansible_does(tmp_path):
    import os
    f = tmp_path / "o.json"; f.write_text(json.dumps(OUT))
    p = subprocess.run([sys.executable, str(HERE / "tfinv.py"), "--list"], capture_output=True, text=True, env={**os.environ, "TFINV_FILE": str(f)})
    assert p.returncode == 0 and "web-01" in p.stdout
