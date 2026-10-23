"""Generate the simulated fleet inventory used by the capstone: 12 nodes (8 web, 4 db), all local-connection, with per-node ports."""
import sys

def inventory_text(python=None):
    python = python or sys.executable
    lines = ["[web]"] + [f"web{i:02d} ansible_connection=local ansible_python_interpreter={python} app_port={8000 + i}" for i in range(1, 9)]
    lines += ["", "[db]"] + [f"db{i:02d} ansible_connection=local ansible_python_interpreter={python} app_port={5400 + i}" for i in range(1, 5)]
    lines += ["", "[servers:children]", "web", "db", "", "[production:children]", "servers", ""]
    return "\n".join(lines)
