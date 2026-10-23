---
description: "Migrating shell scripts to Ansible and avoiding anti-patterns: a script versus a playbook on repeat runs, plus a catalogue of 24 mistakes."
---

# 08 · Migrating Scripts and Avoiding Anti-Patterns

Most teams arrive at Ansible with a pile of shell scripts, wiki instructions and muscle memory. Migrating them well means translating *intent* into declarative tasks, not transliterating commands into `shell:` tasks. This lesson shows the difference with a measured example and then lists the anti-patterns that appear again and again.

!!! note "What was run"
    A small provisioning script and its playbook equivalent were both run repeatedly on a Mac (sandbox directories under `/tmp`), ansible-core 2.21.5. The catalogue of anti-patterns draws on this course's measured findings and on general experience; items not measured here are marked as such.

## The script and its problems

```bash
#!/bin/bash
set -e
D=${1:?dir}
mkdir $D
mkdir $D/logs
echo "port=8080" >> $D/app.conf
useradd_sim() { echo "created user" >> $D/users.log; }
useradd_sim
chmod 600 $D/app.conf
```

Observed:

- **First run**: works.
- **Second run**: `mkdir: /tmp/mig5: File exists`, exit status **1** (because of `set -e`). The script is not rerunnable.
- **Starting from a different state** (the directory exists but is empty): the same failure, even though nothing was wrong with the target state.
- **Without `set -e`**, two runs left `app.conf` containing `port=8080` **twice** (`>>` appends). The script "worked" and corrupted its own output.

This is the typical profile of a provisioning script: it is correct only from one starting state and only once. Fixing it with guards (`mkdir -p`, `grep -q ... || echo`) is possible and tedious, and each guard is a hand-written check of state.

## The playbook version

```yaml
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - ansible.builtin.file: {path: "{{ d }}/logs", state: directory, mode: "0755"}
    - ansible.builtin.lineinfile: {path: "{{ d }}/app.conf", line: "port=8080", regexp: "^port=", create: true, mode: "0600"}
    - ansible.builtin.lineinfile: {path: "{{ d }}/users.log", line: "created user", create: true, mode: "0644"}
```

Measured:

```text
fresh directory, run 1: ok=3 changed=3
run 2:                  ok=3 changed=0
run 3:                  ok=3 changed=0       app.conf: port=8080  (one line)
pre-existing empty dir: ok=3 changed=3      (works from a different starting state)
```

The playbook converges from either starting state, is safe to repeat, and shows in check mode what it would do. (The directory itself is created by `file` with `state: directory` creating parents as needed; the script had a separate `mkdir $D`.)

## How to migrate

1. **Inventory the scripts**: what do they do, to which hosts, how often, who runs them? Delete dead ones.
2. **Write down the intent as end state**: "directory exists with mode 0755", "setting port is 8080", "user exists in group X". If you can't state the end state, you do not yet understand the script.
3. **Map each step to a module** (`ansible-doc -l`, collections). Use `command`/`shell` only where none exists, with `creates`/`removes`/`changed_when` (Level 3 · 04).
4. **Keep the data separate**: ports, paths and names become variables; hosts differences become inventory variables.
5. **Run side by side**: apply the playbook to a copy of a real machine or a staging machine and compare the resulting state with the script's (file lists, `stat`, package lists).
6. **Test idempotence** (Lesson 02) and check mode.
7. **Switch over** one environment at a time; keep the script for a rollback window; then delete it.
8. **Document** the playbook's variables and the run command.

Resist rewriting *and* redesigning in one step. A faithful translation that passes tests first, improvements afterwards.

## Anti-pattern catalogue

Each item has a fix; those measured in this course have a lesson reference.

1. **`shell:` for everything.** No idempotency, no check mode, injection risk. *Use modules; if unavoidable, guard and quote (Level 3 · 04).*
2. **Unguarded commands that report `changed` every run.** *`changed_when`, `creates`/`removes` (Level 1 · 05).*
3. **`ignore_errors: true` as a default.** Hides real failures. *`failed_when` with a specific condition; rescue blocks (Level 2 · 04).*
4. **Variables defined everywhere.** Unpredictable precedence. *One definition per variable; defaults in roles, data in inventory (Level 2 · 02).*
5. **`set_fact` used for configuration.** Outranks inventory. *Use it for computed values only.*
6. **God playbook / God role.** One file that does everything, run with tags. *Split by lifecycle and responsibility (Level 2 · 01, 07).*
7. **Dictionaries expected to merge.** *`combine(recursive=True)` explicitly (Level 2 · 03).*
8. **Deleting a task to remove a feature.** Leaves orphans. *Explicit `state: absent` first (Level 3 · 08).*
9. **Two roles managing one resource.** Never converges. *Single owner; drop-in directories (Level 3 · 08).*
10. **`state: latest` in production runs.** Non-reproducible upgrades. *Pin versions; upgrade deliberately.*
11. **Handlers for things that must happen.** A failure can skip them (Level 1 · 08). *`force_handlers`, or explicit tasks with `when`.*
12. **No input validation.** *`assert` / `argument_specs` at the top of roles (Level 2 · 01).*
13. **Hard-coded shared paths.** Hosts race (Level 2 · 01). *Per-host paths.*
14. **Secrets in plain text, `debug`, or `-vvv` logs.** *Vault, `no_log`, linter (Lesson 03).*
15. **Unpinned dependencies.** *Pin ansible-core, collections, Python libs; use EEs (Lesson 01).*
16. **Short module names.** *FQCNs; lint enforces (Level 2 · 09).*
17. **Tags as dependencies.** `--tags configure` skipping a prerequisite (Level 2 · 07). *Independent tagged tasks, or `always`.*
18. **`hosts: all` with no limit/guard.** *Preflight, limits, protected groups (Lesson 07).*
19. **No tests.** *Lint, second-run test, drift check (Lessons 02, 06).*
20. **Treating the playbook as documentation of what is deployed.** It only says what *would be enforced*; drift and orphans make reality differ. *Audit (Lesson 06).*
21. **Giant Jinja one-liners.** *Compute in `vars` or write a tested filter (Level 3 · 02).*
22. **Fact gathering everywhere.** *Off unless used; cache with expiry (Level 3 · 06).*
23. **Running Ansible from laptops with personal keys against production.** *Controlled runners/controller, per-environment credentials, audit (Lessons 01, 03).*
24. **Using Ansible to hold long-lived state.** *Keep state in the system of record; generate inventory (Lesson 05).*

## When not to use Ansible

Honest limits: very large fleets needing sub-minute convergence (SSH-based push is slow, pull helps); highly dynamic container orchestration (use Kubernetes controllers and GitOps); complex stateful infrastructure graphs (Terraform); real-time event-driven remediation (Ansible has event-driven features in some distributions, not run here); and where a vendor's native tool is the supported path. Ansible shines at configuring heterogeneous machines and orchestrating operational tasks across them.

## How It Actually Works

A shell script is an *imperative program*: it executes commands in order and its outcome depends on the starting state because each command has an implicit precondition (`mkdir` requires the directory not to exist). An Ansible task is a *desired-state assertion* implemented by a module that first reads the current state and acts only on the difference, so preconditions are checked rather than assumed. The migration shifts the burden from the author (writing guards) to the module author (writing the comparison once, tested, in a reusable form). That is why the playbook above has no `if` statements yet converges from two starting states: `file` and `lineinfile` contain them.

## Common mistakes

- **Transliterating commands into `shell` tasks.**
- **Migrating without a side-by-side comparison.**
- **Redesigning while migrating.**
- **Keeping the script as a second source of truth.**
- **No owner for the new playbook.**
- **Converting everything at once** instead of one environment or service at a time.

## Exercise

1. Pick a script you run today. Write the end-state list for it, then the playbook. Compare the script and playbook on three starting states.
2. Take five items from the anti-pattern catalogue and find an example in your own repositories; write the fix.
3. Write a lint rule or test that detects anti-pattern 8 (a removed task without an explicit absent step) in your repo's history, or explain why it cannot be detected statically.
4. Decide which of your current automation tasks should *not* be in Ansible and say where they should live.
