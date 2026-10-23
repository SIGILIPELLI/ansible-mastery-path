#!/usr/bin/env python3
"""Dynamic inventory SCRIPT: reads cmdb.csv and prints inventory JSON. Protocol: `--list` prints everything; `--host NAME` prints that host's vars (here {} because --list includes _meta.hostvars)."""
import csv, json, sys
from pathlib import Path

def build(path):
    inv = {"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            name = row["name"]
            inv["_meta"]["hostvars"][name] = {"ansible_host": row["address"], "http_port": int(row["port"]), "ansible_connection": "local"}
            for g in (row["role"], row["env"]):
                inv.setdefault(g, {"hosts": []})["hosts"].append(name)
    return inv

def main(argv):
    path = Path(__file__).with_name("cmdb.csv")
    if "--list" in argv:
        print(json.dumps(build(path), indent=2)); return 0
    if "--host" in argv:
        print(json.dumps({})); return 0
    print("usage: inventory_script.py --list | --host NAME", file=sys.stderr); return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
