---
description: "Capstone: operate a simulated 12-node fleet with the course tools: lint, converge, idempotence, drift audit, preflight guard and targeted repair."
---

# 10 · Capstone — Managing a Simulated Fleet

The capstone operates a fleet end to end with the tools built across the course. The fleet is simulated: twelve inventory hosts (eight `web`, four `db`) that all use `ansible_connection=local`, each owning a directory tree under a temporary sandbox. The playbook is the lint-clean baseline from Level 1 (`baseline_ci.yml`). The test file `src/l4/capstone/test_capstone.py` walks through a realistic operating sequence with real `ansible-playbook`, `ansible-lint` and the audit and guard tools.

!!! note "What was run, and what wasn't"
    All nine tests passed (about 42 seconds) with ansible-core 2.21.5 on a Mac. **No remote hosts, SSH, privilege escalation, packages, services or networks were involved**; the "servers" are directories and the managed state is files and modes. The sequence demonstrates the *workflow and the tools*; it does not prove anything about a real fleet. See the "What this does not show" section.

## The fleet

```text
[web]  web01..web08   app_port 8001..8008
[db]   db01..db04     app_port 5401..5404
[servers:children]  web, db
[production:children] servers
```

The fleet inventory is generated (`fleet.py`) with each host's `ansible_python_interpreter` set to the Python running the tests. `production` contains everything via nested groups, which is exactly the shape that broke the first version of the preflight guard (Lesson 07).

## The sequence, as tests

The tests share one fleet (module-scoped sandbox) and run in order, because operations on a fleet are a story, not independent cases:

| # | Step | Assertion |
|---|---|---|
| 1 | Secret hygiene | `nologlint` finds nothing in the playbook |
| 2 | Lint | `ansible-lint` passes (production profile) |
| 3 | First converge | All 12 nodes `changed=6`, no failures |
| 4 | Idempotence | Second run `changed=0` on all 12 |
| 5 | **Drift injected and audited** | Three kinds of drift on three nodes; the audit reports exactly `db02`, `web03`, `web07`, exits 1, and **repairs nothing** |
| 6 | **Preflight** | `all` is refused (exceeds `--max-hosts 5`); a single production node is refused without `--allow-protected`; a three-node list with `--allow-protected` passes |
| 7 | **Targeted repair** | `--limit web03,db02,web07`: only those three hosts run and change; four untouched nodes' `app.conf` modification times are **unchanged** |
| 8 | Audit again | Clean: exit 0, no drifted hosts |
| 9 | Per-node variables survived | `web03` still has `port = 8003`, `db02` has `port = 5402` |

The drift in step 5 was: overwritten application config on `web03` (content drift), mode 777 on `db02`'s data directory (permission drift), and a deleted `motd` on `web07` (missing file). The audit identified exactly the three affected hosts out of twelve and did not touch the broken files (the test asserts the bad config text and the missing file are still as left).

## What the sequence demonstrates

1. **Gates before action.** Static checks and idempotence tests give confidence the playbook is safe to run (Lessons 02 and 03, Level 2 · 09).
2. **Observation before intervention.** The audit tells you what is wrong without changing anything (Lesson 06), and it identifies hosts and tasks, not just a number.
3. **Constraining the blast radius.** The preflight guard stops a fleet-wide run and requires an explicit statement of intent for production (Lesson 07).
4. **Surgical repair.** `--limit` to the drifted hosts leaves everything else alone, shown by unchanged timestamps (Level 2 · 07).
5. **Verification.** A second audit proves the repair worked.
6. **Variables survive repair.** Per-host data (ports) is the same after repair as before.

This is the shape of routine fleet operations: detect, scope, repair narrowly, verify.

## What this does not show

State plainly, because a simulation is easy to over-read:

- **Real connections**: SSH keys, host keys, latency, timeouts, `become`, reboots.
- **Real resources**: packages and services, whose modules have different check-mode behaviour and failure modes; kernel settings; firewall and network changes.
- **Scale**: twelve nodes with local processes say nothing about thousands of hosts, forks, or controller load (Level 3 · 06 measured forks on 20 local hosts only).
- **Concurrency with humans**: people changing the machines while automation runs.
- **Rolling updates and failure budgets** (Level 3 · 07 tests those separately, with the surprise about `always`).
- **Credentials and secrets** beyond the executable-password-script test in Lesson 03.
- **Controllers, pull mode at scale, or Windows/network targets.**

If you carry these ideas into production, rebuild the tests against disposable real targets (VMs or containers for file/package behaviour, a staging fleet for the rest).

## Everything built in this course

All code is under `src/` in the repository, with tests that run the real Ansible (`ansible-core` 2.21.5) unless noted:

| Level | Artefacts | Tests |
|---|---|---|
| 1 | Baseline playbook with 2 simulated servers; handlers/loops/templates experiments | 8 (`baseline/test_baseline.py`) |
| 2 | `webapp` role (with lint passing); variable-precedence experiment; vault, tags, serial experiments | 9 (`l2/test_role.py`) + 5 (`l2/prec/test_precedence.py`, covering the measured order and four pairwise rules) |
| 3 | `kvfile` and `filehash` modules; filter, lookup and inventory plugins; rolling-update playbook | 25 + 23 + 11 |
| 4 | Drift-report callback and audit tool; no_log linter; Terraform-output inventory; preflight guard; CI script; capstone | 9 + 12 + 10 + 9 + 9 |

Counted with `pytest --collect-only`: 8 + 9 + 5 + 25 + 23 + 11 + 9 + 12 + 10 + 9 + 9 = **130 tests** across the course's own code. Several suites start many Ansible processes, so the complete run takes a few minutes (the single biggest are the baseline, rolling-update, drift-audit and capstone suites).

## Where to go from here

1. **Run it on real machines.** Create two VMs or containers and port the baseline to real `package`, `service` and `user` tasks. Keep the second-run test.
2. **Put it in CI** (Lesson 02), and read the CI/CD Mastery Path alongside.
3. **Learn your platform's collections** (cloud, network, Windows) and read their modules' check-mode support.
4. **Try a controller** (AWX) and an execution environment build with a real container runtime.
5. **Combine** with Terraform (Lesson 05) and Kubernetes/GitOps where they fit.
6. **Read other people's roles** critically, with the anti-pattern catalogue (Lesson 08) in hand.

## How It Actually Works

Each capstone step uses an Ansible property you have now seen measured: modules compare state and report `changed` truthfully (so `changed=0` means converged); check mode asks the same modules to report without writing (so the audit changes nothing); `--limit` evaluates a pattern on the controller and never contacts excluded hosts (so repair touches only the drifted three, visible in untouched modification times); and the callback API exposes per-task results to plugins (so the audit can name hosts and items). The preflight guard asks Ansible itself which hosts a pattern selects and combines that with the inventory's group graph. Nothing here relies on magic: it is the same primitives from Level 1 composed with small, tested programs around them.

## Common mistakes

- **Reading a passing simulation as proof for production.**
- **Skipping the audit before repair** (so you can't tell what the repair changed).
- **Repairing the whole fleet** when three hosts drifted.
- **No verification after repair.**
- **Letting a guard rail become a flag everyone passes by default.**
- **Letting the tests rot** when the playbook changes.

## Exercise

1. Run `pytest src/l4/capstone` and read the fixture and each step. Add a thirteenth node and make the tests pass.
2. Add a fourth kind of drift (an extra unmanaged file in `etc/app`) and extend the playbook plus the audit to detect it (use the purge pattern in check mode).
3. Add a rolling-update step to the capstone using `src/l3/rolling` and assert that capacity (hosts in rotation) never drops below a threshold between batches.
4. Write the operations runbook for this fleet: daily audit, how to read the report, when to repair, who approves production, and how to roll back.
