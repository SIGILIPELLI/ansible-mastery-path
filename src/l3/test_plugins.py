"""Tests for filter, lookup, and dynamic-inventory plugins (script and plugin forms)."""
import json, os, subprocess, sys
from pathlib import Path
import pytest
HERE = Path(__file__).parent
BIN = Path(sys.executable).parent
sys.path.insert(0, str(HERE / "filter_plugins"))
try:
    import course_filters as cf
    from ansible.errors import AnsibleFilterError
except ImportError:
    pytest.skip("ansible-core not importable", allow_module_level=True)
ENV = {**os.environ, "ANSIBLE_NOCOLOR": "1", "ANSIBLE_HOME": str(HERE / ".ansible_home"), "ANSIBLE_INVENTORY_PLUGINS": str(HERE / "inventory_plugins"),
       "ANSIBLE_FILTER_PLUGINS": str(HERE / "filter_plugins"), "ANSIBLE_LOOKUP_PLUGINS": str(HERE / "lookup_plugins"), "ANSIBLE_INVENTORY_ENABLED": "script,csvinv,ini,yaml"}

@pytest.mark.parametrize("n,expected", [(0, "0 B"), (1023, "1023 B"), (1024, "1.0 KiB"), (1536, "1.5 KiB"), (1048576, "1.0 MiB"), (5368709120, "5.0 GiB")])
def test_human_bytes(n, expected): assert cf.human_bytes(n) == expected
def test_human_bytes_decimal_base(): assert cf.human_bytes(1000, base=1000) == "1.0 KiB"
@pytest.mark.parametrize("bad", [-1, "abc", None])
def test_human_bytes_rejects(bad):
    with pytest.raises(AnsibleFilterError): cf.human_bytes(bad)
def test_kv_to_dict(): assert cf.kv_to_dict("a=1\n# c\n\nb = two") == {"a": "1", "b": "two"}
def test_kv_to_dict_value_may_contain_equals(): assert cf.kv_to_dict("u=http://x?a=b") == {"u": "http://x?a=b"}
def test_kv_to_dict_bad_line():
    with pytest.raises(AnsibleFilterError): cf.kv_to_dict("novalue")
def test_mask_secrets_nested():
    assert cf.mask_secrets({"user": "u", "db_password": "p", "n": {"api_token": "t", "ok": 1}, "l": [{"secret_x": 1}]}) == {"user": "u", "db_password": "********", "n": {"api_token": "********", "ok": 1}, "l": [{"secret_x": "********"}]}
def test_mask_secrets_does_not_mutate(): d = {"password": "p"}; cf.mask_secrets(d); assert d == {"password": "p"}
def test_filter_registration(): assert set(cf.FilterModule().filters()) == {"human_bytes", "kv_to_dict", "mask_secrets"}

def test_inventory_script_protocol():
    out = subprocess.run([str(HERE / "inventory_script.py"), "--list"], capture_output=True, text=True)
    data = json.loads(out.stdout); assert out.returncode == 0 and "_meta" in data and set(data["web"]["hosts"]) == {"web-01", "web-02", "web-stg"}
def test_inventory_script_host_returns_json_object():
    assert json.loads(subprocess.run([str(HERE / "inventory_script.py"), "--host", "web-01"], capture_output=True, text=True).stdout) == {}
def test_inventory_script_usage_error():
    assert subprocess.run([str(HERE / "inventory_script.py")], capture_output=True, text=True).returncode == 2
@pytest.mark.skipif(not (BIN / "ansible-inventory").exists(), reason="ansible not installed")
@pytest.mark.parametrize("src", ["inventory_script.py", "cmdb.csv.yml"])
def test_script_and_plugin_produce_identical_inventories(src):
    out = subprocess.run([str(BIN / "ansible-inventory"), "-i", str(HERE / src), "--list"], capture_output=True, text=True, env=ENV, cwd=HERE)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout); hv = data["_meta"]["hostvars"]
    unwrap = lambda v: v["__ansible_unsafe"] if isinstance(v, dict) and "__ansible_unsafe" in v else v     # measured: strings set by the inventory PLUGIN are shown with this marker (untrusted: never templated)
    hv = {h: {k: unwrap(v) for k, v in d.items()} for h, d in hv.items()}
    assert set(hv) == {"web-01", "web-02", "db-01", "web-stg"} and hv["db-01"]["http_port"] == 5432 and hv["web-01"]["ansible_host"] == "10.0.1.11"
    assert set(data["prod"]["hosts"]) == {"web-01", "web-02", "db-01"} and data["staging"]["hosts"] == ["web-stg"]
@pytest.mark.skipif(not (BIN / "ansible").exists(), reason="ansible not installed")
def test_lookup_plugin_reads_file(tmp_path):
    env_file = tmp_path / "x.env"; env_file.write_text('A=1\nB="two"\n')
    out = subprocess.run([str(BIN / "ansible"), "localhost", "-m", "debug", "-a", f"msg={{{{ lookup('envfile', 'A', 'B', file='{env_file}') }}}}", "-e", f"ansible_python_interpreter={sys.executable}"], capture_output=True, text=True, env=ENV, cwd=HERE)
    assert '"msg": "1,two"' in out.stdout, out.stdout + out.stderr          # measured: several results are joined with commas into ONE string by default
    out2 = subprocess.run([str(BIN / "ansible"), "localhost", "-m", "debug", "-a", f"msg={{{{ lookup('envfile', 'A', 'B', file='{env_file}', wantlist=True) }}}}", "-e", f"ansible_python_interpreter={sys.executable}"], capture_output=True, text=True, env=ENV, cwd=HERE)
    assert '"1"' in out2.stdout and '"two"' in out2.stdout and "1,two" not in out2.stdout, out2.stdout + out2.stderr
@pytest.mark.skipif(not (BIN / "ansible").exists(), reason="ansible not installed")
def test_lookup_missing_key_errors(tmp_path):
    env_file = tmp_path / "x.env"; env_file.write_text('A=1\n')
    out = subprocess.run([str(BIN / "ansible"), "localhost", "-m", "debug", "-a", f"msg={{{{ lookup('envfile', 'Z', file='{env_file}') }}}}"], capture_output=True, text=True, env=ENV, cwd=HERE)
    assert "key 'Z' not in" in out.stdout + out.stderr
