#!/usr/bin/env python3
"""preflight: compute the blast radius of a planned run BEFORE running it, from `ansible-inventory --list` JSON and an optional limit pattern evaluated by `ansible --list-hosts`.
Refuses (exit 1) when the number of target hosts exceeds --max-hosts, or any protected group is hit without --allow-protected."""
import argparse, json, subprocess, sys
from pathlib import Path

def target_hosts(inventory, pattern, ansible_bin=None):
    ansible_bin = ansible_bin or str(Path(sys.executable).parent / "ansible")
    p = subprocess.run([ansible_bin, pattern, "-i", str(inventory), "--list-hosts"], capture_output=True, text=True)
    hosts = [l.strip() for l in p.stdout.splitlines() if l.startswith("    ")]
    return hosts

def groups_of(inv_json, hosts):
    """Group membership INCLUDING ancestors: a host in web is also in production when production has child web."""
    direct, children = {}, {}
    for g, data in inv_json.items():
        if g == "_meta" or not isinstance(data, dict): continue
        children[g] = list(data.get("children", []))
        for h in data.get("hosts", []): direct.setdefault(h, set()).add(g)
    parents = {}
    for g, kids in children.items():
        for k in kids: parents.setdefault(k, set()).add(g)
    def ancestors(g, seen=None):
        seen = seen or set()
        for p in parents.get(g, ()):
            if p not in seen: seen.add(p); ancestors(p, seen)
        return seen
    out = {}
    for h in hosts:
        gs = set(direct.get(h, ()))
        for g in list(gs): gs |= ancestors(g)
        out[h] = sorted(gs)
    return out

def assess(hosts, host_groups, max_hosts, protected, allow_protected):
    reasons = []
    if not hosts: reasons.append("pattern matches no hosts")
    if len(hosts) > max_hosts: reasons.append(f"{len(hosts)} hosts exceeds --max-hosts {max_hosts}")
    hit = sorted({g for h in hosts for g in host_groups.get(h, []) if g in protected})
    if hit and not allow_protected: reasons.append(f"touches protected group(s): {', '.join(hit)} (use --allow-protected)")
    return reasons

def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument("inventory"); ap.add_argument("pattern"); ap.add_argument("--max-hosts", type=int, default=5)
    ap.add_argument("--protected", default="production"); ap.add_argument("--allow-protected", action="store_true"); a = ap.parse_args(argv)
    inv = json.loads(subprocess.run([str(Path(sys.executable).parent / "ansible-inventory"), "-i", a.inventory, "--list"], capture_output=True, text=True, check=True).stdout)
    hosts = target_hosts(a.inventory, a.pattern); reasons = assess(hosts, groups_of(inv, hosts), a.max_hosts, set(a.protected.split(",")), a.allow_protected)
    print(f"targets: {len(hosts)} host(s): {', '.join(hosts[:10])}{' ...' if len(hosts) > 10 else ''}")
    for r in reasons: print("REFUSED:", r)
    return 1 if reasons else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
