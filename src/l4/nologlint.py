#!/usr/bin/env python3
"""nologlint: flag tasks that use secret-looking variables but lack `no_log: true`.
Heuristic (text based): a task is flagged when its arguments reference a variable whose name contains password/secret/token/api_key/private_key or begins with vault_,
and neither the task nor an enclosing block sets no_log: true. Tasks using the `ansible.builtin.debug` module are flagged regardless (they print)."""
import re, sys
from pathlib import Path
import yaml

SECRET_NAME = re.compile(r"(password|passwd|secret|token|api_?key|private_?key|credential)|^vault_", re.I)
JINJA = re.compile(r"\{\{(.*?)\}\}", re.S)
TASK_KEYWORDS = {"name", "when", "register", "tags", "notify", "loop", "with_items", "become", "become_user", "vars", "environment", "delegate_to", "run_once", "ignore_errors",
                 "changed_when", "failed_when", "no_log", "block", "rescue", "always", "until", "retries", "delay", "args", "check_mode", "diff", "listen", "loop_control", "async", "poll"}

def secret_vars(text):
    found = set()
    for expr in JINJA.findall(text):
        for ident in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr):
            if SECRET_NAME.search(ident): found.add(ident)
    return found

def walk(tasks, inherited_no_log, where, out):
    for i, t in enumerate(tasks or []):
        if not isinstance(t, dict): continue
        no_log = inherited_no_log or bool(t.get("no_log"))
        label = t.get("name") or f"task #{i + 1}"
        for key in ("block", "rescue", "always"):
            if key in t: walk(t[key], no_log, f"{where}/{label}", out)
        module_keys = [k for k in t if k not in TASK_KEYWORDS]
        body = yaml.safe_dump({k: t[k] for k in module_keys} | {"environment": t.get("environment"), "vars": t.get("vars")}, default_flow_style=False) if module_keys else ""
        names = secret_vars(body)
        is_debug = any(k.endswith("debug") for k in module_keys)
        if names and (not no_log or is_debug):
            out.append((where, label, sorted(names), "debug prints it" if is_debug else "missing no_log"))

def lint_text(text, path="<string>"):
    out = []
    docs = yaml.safe_load(text)
    if isinstance(docs, list):
        for play in docs:
            if not isinstance(play, dict): continue
            for section in ("pre_tasks", "tasks", "post_tasks", "handlers"):
                walk(play.get(section), bool(play.get("no_log")), f"{path}:{play.get('name', 'play')}:{section}", out)
    return out

def main(argv):
    findings = []
    for p in argv:
        findings += lint_text(Path(p).read_text(), p)
    for where, label, names, why in findings: print(f"{where}: '{label}' uses {', '.join(names)} -> {why}")
    print(f"{len(findings)} finding(s)")
    return 1 if findings else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
