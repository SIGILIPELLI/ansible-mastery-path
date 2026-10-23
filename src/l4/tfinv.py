#!/usr/bin/env python3
"""tfinv: build an Ansible inventory from `terraform output -json`.
Expected output shape (from the Terraform CLI docs, hand-written fixture in tests): {"web_ips": {"value": [...], "type": [...], "sensitive": false}, "db": {"value": {"address": "..", ...}}}
Convention used here: output `web_ips` -> group web; `db_hosts` -> group db. Never run against a real state by this course. Sensitive outputs are refused."""
import json, sys

GROUPS = {"web_ips": "web", "db_hosts": "db", "bastion_ip": "bastion"}

def build(tf_output):
    inv = {"_meta": {"hostvars": {}}}
    for out_name, group in GROUPS.items():
        if out_name not in tf_output: continue
        entry = tf_output[out_name]
        if entry.get("sensitive"): raise ValueError(f"output {out_name!r} is sensitive; refusing to put it in inventory")
        value = entry["value"]
        addrs = value if isinstance(value, list) else [value]
        names = []
        for i, a in enumerate(addrs, 1):
            if not isinstance(a, str) or not a: raise ValueError(f"output {out_name!r} item {i} is not a non-empty string: {a!r}")
            name = f"{group}-{i:02d}"
            inv["_meta"]["hostvars"][name] = {"ansible_host": a, "tf_output": out_name}
            names.append(name)
        inv[group] = {"hosts": names}
    if not inv["_meta"]["hostvars"]: raise ValueError("no known outputs found (expected one of: %s)" % ", ".join(GROUPS))
    return inv

def main(argv):
    if len(argv) == 1 and argv[0] in ("--list",):
        import os
        raw = open(os.environ["TFINV_FILE"]).read() if os.environ.get("TFINV_FILE") else sys.stdin.read()      # Ansible calls the script with only --list; the file comes from the environment
    elif len(argv) == 2 and argv[0] == "--list":
        raw = open(argv[1]).read()
    elif argv[:1] == ["--host"]:
        print("{}"); return 0
    else:
        print("usage: tfinv.py --list [terraform-output.json]  (or stdin)", file=sys.stderr); return 2
    try:
        print(json.dumps(build(json.loads(raw)), indent=2)); return 0
    except (ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"tfinv: {exc}", file=sys.stderr); return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
