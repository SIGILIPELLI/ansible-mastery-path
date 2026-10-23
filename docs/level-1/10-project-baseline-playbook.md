---
description: "Level 1 project: a baseline playbook for two simulated servers with 8 pytest tests running real ansible-playbook for idempotency, drift and handlers."
---

# 10 · Project — A Verified Baseline Playbook

A playbook you have never tested twice is a playbook you hope works. This project builds a small **server baseline** and, more importantly, an automated test suite that runs the **real `ansible-playbook`** and asserts the properties from this level: it converges, it is idempotent, check mode touches nothing, drift is detected and repaired, and handlers fire only when they should.

!!! note "What was run, and what wasn't"
    The tests call the real `ansible-playbook` (ansible-core 2.21.5) on a Mac. The "servers" `node1` and `node2` are two inventory entries with `ansible_connection=local`, each owning a directory tree under a temporary sandbox (`<sandbox>/<host>/etc/...`). **No real server, SSH, package manager, `systemd`, user account, or privilege escalation was involved**, so this baseline manages files and directories only. A production baseline would add packages, users, services and firewall rules, each of which needs its own verification on the target OS. All 8 tests passed on the first full run (53 seconds, because each test starts several Ansible processes).

## What the playbook manages

`src/baseline/baseline.yml` configures every host in `servers`:

1. **Directory tree** with modes (`etc/app` 0755, `var/log/app` 0750, `var/lib/app` 0700) via a loop with a short `label`.
2. **Message of the day** with `copy` content.
3. **Application config** from a template (`templates/app.conf.j2`) using a per-host variable `app_port` (8080 for `node1`, 9090 for `node2`) and an optional `workers` variable. It notifies the `restart app` handler.
4. **A hardening line** in a copy of `sshd_config`: `lineinfile` replaces any `#?PermitRootLogin` line with `PermitRootLogin no`, creating the file at mode 0600 if absent.
5. **A managed block** in `sysctl.conf` with `blockinfile` (two settings between marker comments).
6. **A handler** that increments `var/lib/app/restart.count`, standing in for restarting the service: it lets the tests count how many restarts happened.

Running it for real:

```text
first run : node1 ok=6 changed=6   node2 ok=6 changed=6
second run: node1 ok=5 changed=0   node2 ok=5 changed=0
```

(The first run is `ok=6` because the handler ran once; the second has no handler, so `ok=5`.)

## Drift, shown for real

I then vandalised `node1` by hand: appended `port = 1` to `app.conf`, set the `var/lib/app` directory to mode 777, and changed `PermitRootLogin no` to `yes`. Running with `--check --diff`:

```text
TASK [directory tree]
-    "mode": "0777"
+    "mode": "0700"
changed: [node1] => (item=var/lib/app)
TASK [app configuration]
-port = 1
changed: [node1]
TASK [ensure a hardening line in sshd config copy]
-PermitRootLogin yes
+PermitRootLogin no
changed: [node1]
recap: node1 ok=6 changed=4    node2 ok=5 changed=0
```

Four reported changes on `node1` (three drifted items plus the handler that the config change would trigger) and none on `node2`. Then a real run repaired everything; `restart.count` ended at 2 (one restart after the first deployment, one after the repair; check mode itself did not write).

This is the whole value of check mode in operations: **the diff is the drift report**, and it distinguishes hosts that match from hosts that do not.

## The test suite

`src/baseline/test_baseline.py` starts Ansible with `subprocess`, passes the sandbox location with `-e sandbox=<tmp path>`, parses the `PLAY RECAP` lines into dictionaries of counters, and asserts:

| Test | What it proves |
|---|---|
| First run changes everything | Both nodes show `changed=6`, exit status 0 |
| Second run is idempotent | `changed=0` and `failed=0` on every node |
| Check mode writes nothing | On a fresh sandbox, `--check` reports at least 5 changes and **the sandbox directory does not exist afterwards** |
| Per-host variable reaches template | `node1` file contains `port = 8080`, `node2` contains `port = 9090` |
| Modes are enforced | `var/lib/app` is 0700 and `sshd_config` is 0600 (`stat`) |
| Drift detected, then repaired | After appending `port = 1`: check mode reports changes only for `node1` and leaves the bad line; a real run removes it; a further run is `changed=0` |
| Handler runs only on config change | Counter is 1 after the first run, still 1 after an unchanged re-run, 2 after running with `-e workers=4` |
| Manual edit of `sshd_config` is reverted | A file containing `PermitRootLogin yes` is rewritten to `PermitRootLogin no` |

Design notes on the harness:

- It rewrites the inventory in a temporary copy so the interpreter path points at the Python running pytest, instead of a hard-coded path.
- It sets `ANSIBLE_HOME` to a directory beside the test so Ansible's temp files and cache stay out of your real home directory.
- It skips itself with a clear reason if `ansible-playbook` is not installed (`pytest.mark.skipif`).
- Because every test runs Ansible several times, the suite is slow (53 s). That is the honest cost of testing the real thing. Level 2 · 09 covers lighter-weight checks (`ansible-lint`, `--syntax-check`) and how to keep slow tests in a separate stage.

## How to use this pattern on a real baseline

1. Write the invariant first: "after the playbook, SSH root login is disabled, the log directory is 0750, the service is enabled."
2. Express each invariant as a task (so Ansible enforces it) **and** as a test assertion (so you notice if the task is removed).
3. Always include the **second-run-is-zero-changes** test. It is the cheapest and most valuable test you can write for a playbook.
4. Add a **drift test** for any setting an operator might change by hand.
5. Run the same tests in CI against disposable machines (containers or VMs), as Level 4 · 02 describes. Containers are good for file and package logic; for anything involving the init system or kernel settings, use a VM, since containers share the host kernel.

## How It Actually Works

Check mode and idempotency both come from how modules are written. Each file-oriented module computes the current state on the target, compares it with the requested state, and only writes if they differ; in check mode the same code runs but the write step is skipped and the module reports `changed` based on the comparison. The test suite exploits this: because the recap counts come from the modules' own `changed` flags, `changed=0` on the second run is a direct measurement that every module found the system already in the desired state. The handler counter works because handlers run only if at least one notifying task reported `changed` (Lesson 08), and the check-mode test works because `check` is a property of the whole run: no module writes, so the sandbox directory never gets created even though `file` would have created it.

## Common mistakes

- **Testing only the first run.** Idempotency failures appear on the second.
- **Tests that share state** between runs. Each test here uses a fresh temporary sandbox.
- **Checking only the exit status.** A playbook can exit 0 and have done nothing (zero hosts) or changed the wrong thing.
- **Putting secrets in test inventories.**
- **Assuming file-only tests prove package/service behaviour.**
- **Letting the suite get too slow** and then skipping it.

## Exercise

1. Run `python3 -m pytest -q src/baseline` (with `ansible-core` installed) and read the recap parsing code. Add a third node with `app_port=7070` and extend the tests.
2. Add a task that sets a file's content from `ansible_date_time` and watch the idempotency test fail; then fix the task.
3. Add a managed setting to `sysctl.conf`, a test that a hand-edited value inside the managed block is reverted, and a test that a line outside the block is preserved.
4. Write the invariants list for a baseline of a Linux web server (ten items) and mark which could be tested with file-only checks and which need a real VM.
