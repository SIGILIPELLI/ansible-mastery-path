"""Pins the variable precedence measured on ansible-core 2.21.5 (highest first). If a future version changes it, this test fails and the lesson needs updating."""
import shutil, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent))
pytestmark = pytest.mark.skipif(not (Path(sys.executable).parent / "ansible-playbook").exists(), reason="ansible-playbook not installed")
import run
EXPECTED = ["extra_vars", "set_fact", "include_vars", "task_vars", "role_vars", "play_vars_files", "play_vars", "inv_host_vars", "inv_file_host", "inv_group_vars_web", "inv_group_vars_all", "inv_file_group_web", "inv_file_group_all", "role_defaults"]
def test_measured_order(): assert run.measure() == EXPECTED
def test_pairwise_extra_vars_beats_everything(tmp_path):
    for s in run.SOURCES[:-1]: assert run.winner(tmp_path / "w", [s, "extra_vars"]) == "extra_vars"
def test_host_beats_group_in_each_location(tmp_path):
    assert run.winner(tmp_path / "w", ["inv_group_vars_web", "inv_host_vars"]) == "inv_host_vars"
    assert run.winner(tmp_path / "w", ["inv_file_group_web", "inv_file_host"]) == "inv_file_host"
def test_specific_group_beats_all(tmp_path):
    assert run.winner(tmp_path / "w", ["inv_group_vars_all", "inv_group_vars_web"]) == "inv_group_vars_web"
def test_role_defaults_lose_to_everything(tmp_path):
    for s in run.SOURCES[1:]: assert run.winner(tmp_path / "w", ["role_defaults", s]) == s
