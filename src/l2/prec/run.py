"""Find Ansible's variable precedence EMPIRICALLY: set `x` in many places, run, see who wins, remove the winner, repeat."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ANS = Path(sys.executable).parent
SOURCES = ["role_defaults", "inv_file_group_all", "inv_file_group_web", "inv_group_vars_all", "inv_group_vars_web", "inv_file_host", "inv_host_vars", "play_vars", "play_vars_files", "role_vars", "task_vars", "include_vars", "set_fact", "extra_vars"]

def build(root, active):
    root = Path(root); shutil.rmtree(root, ignore_errors=True); (root / "roles/r/defaults").mkdir(parents=True); (root / "roles/r/vars").mkdir(parents=True); (root / "roles/r/tasks").mkdir(parents=True)
    (root / "group_vars").mkdir(); (root / "host_vars").mkdir()
    py = str(ANS / "python")
    ini = ["[web]", "h1 ansible_connection=local" + (" x=inv_file_host" if "inv_file_host" in active else ""), "", "[all:vars]", f"ansible_python_interpreter={py}"]
    if "inv_file_group_all" in active: ini.append("x=inv_file_group_all")
    ini += ["", "[web:vars]"] + (["x=inv_file_group_web"] if "inv_file_group_web" in active else [])
    (root / "hosts.ini").write_text("\n".join(ini) + "\n")
    if "inv_group_vars_all" in active: (root / "group_vars/all.yml").write_text("x: inv_group_vars_all\n")
    if "inv_group_vars_web" in active: (root / "group_vars/web.yml").write_text("x: inv_group_vars_web\n")
    if "inv_host_vars" in active: (root / "host_vars/h1.yml").write_text("x: inv_host_vars\n")
    if "role_defaults" in active: (root / "roles/r/defaults/main.yml").write_text("x: role_defaults\n")
    if "role_vars" in active: (root / "roles/r/vars/main.yml").write_text("x: role_vars\n")
    (root / "extra.yml").write_text("x: play_vars_files\n"); (root / "inc.yml").write_text("x: include_vars\n")
    task = []
    if "include_vars" in active: task.append("- ansible.builtin.include_vars: inc.yml")
    if "set_fact" in active: task.append("- ansible.builtin.set_fact: {x: set_fact}")
    task.append("- ansible.builtin.debug: {msg: 'X={{ x | default(\"UNSET\") }}'}" if "task_vars" not in active else "- ansible.builtin.debug: {msg: 'X={{ x | default(\"UNSET\") }}'}\n  vars: {x: task_vars}")
    (root / "roles/r/tasks/main.yml").write_text("\n".join(task) + "\n")
    play = ["- hosts: web", "  gather_facts: false"]
    if "play_vars" in active: play += ["  vars: {x: play_vars}"]
    if "play_vars_files" in active: play += ["  vars_files: [extra.yml]"]
    play += ["  roles: [r]"]
    (root / "site.yml").write_text("\n".join(play) + "\n")

def winner(root, active):
    build(root, active); cmd = [str(ANS / "ansible-playbook"), "-i", "hosts.ini", "site.yml"] + (["-e", "x=extra_vars"] if "extra_vars" in active else [])
    out = subprocess.run(cmd, cwd=root, capture_output=True, text=True, env={**os.environ, "ANSIBLE_NOCOLOR": "1", "ANSIBLE_LOCALHOST_WARNING": "False", "ANSIBLE_INVENTORY_UNPARSED_WARNING": "False", "ANSIBLE_HOME": str(Path(root) / ".home")})
    for line in out.stdout.splitlines():
        if "X=" in line: return line.split("X=")[1].split('"')[0].strip()
    raise RuntimeError(out.stdout[-800:] + out.stderr[-800:])

def measure():
    root = tempfile.mkdtemp(); active = list(SOURCES); order = []
    while active:
        w = winner(root, active); order.append(w); active.remove(w)
        if w == "UNSET": break
    return order

if __name__ == "__main__":
    for i, s in enumerate(measure(), 1): print(i, s)
