---
description: "State, drift and convergence: removed tasks leave orphans, two tasks can fight forever, and a purge pattern; each shown by running."
---

# 08 · State, Drift and Convergence

Terraform records what it created, so removing a resource from the code removes it from the world. Ansible records nothing. It looks at the host, compares, and fixes only what your tasks mention. That makes Ansible simple and flexible, and it makes three problems your job: **orphans** (things you used to manage), **conflicts** (two tasks managing the same thing differently), and **drift** (the host changing between runs).

!!! note "What was run"
    The three experiments below are real runs of small playbooks (`state_v1/v2/v3.yml`, `flip.yml` in `src/l3`) in a sandbox directory on a Mac with ansible-core 2.21.5. They manage files; the same logic applies to packages, users, services and firewall rules, whose modules were not run.

## No state file: orphans

Version 1 of a playbook manages two files:

```yaml
- copy: {dest: "{{ d }}/a.conf", content: "a\n"}
- copy: {dest: "{{ d }}/legacy.conf", content: "legacy\n"}
```

Run: `ok=2 changed=2`; both files exist. Version 2 removes the `legacy` task because the feature was retired:

```text
state_v2.yml: ok=1 changed=0
files after v2: a.conf legacy.conf        <-- legacy.conf is still there
```

Ansible has no record that it ever created `legacy.conf`, so deleting the task changes **nothing** on the host. The retired configuration keeps working on every machine that received version 1 (and does not exist on new machines, so your fleet is now inconsistent). This is the most important difference from state-based tools.

### Fix 1: explicit removal

Add a task for the retirement and keep it until every environment has run it:

```yaml
- ansible.builtin.file: {path: "{{ d }}/legacy.conf", state: absent}
```

Remove it later when you are sure nothing needs it (tracked in a changelog). This is the normal approach for packages, users and services (`state: absent`).

### Fix 2: allow-list purge

For directories where only managed files should exist, enumerate and delete everything else:

```yaml
vars: {managed: [a.conf]}
tasks:
  - ansible.builtin.copy: {dest: "{{ d }}/a.conf", content: "a\n"}
  - ansible.builtin.find: {paths: "{{ d }}", patterns: "*.conf"}
    register: found
  - ansible.builtin.file: {path: "{{ item.path }}", state: absent}
    loop: "{{ found.files }}"
    loop_control: {label: "{{ item.path | basename }}"}
    when: item.path | basename not in managed
```

In `--check` the purge showed `changed: [localhost] => (item=legacy.conf)` and nothing was deleted; the real run removed it (`files after v3: a.conf`). This is powerful and dangerous: a typo in the allow-list or the wrong directory deletes real files. Safeguards: restrict `paths` and `patterns` tightly, always preview with `--check`, make the playbook refuse to run if `managed` is empty, and keep backups. Many tools use this pattern for `sudoers.d`, `cron.d`, `conf.d` directories ("drop-in" directories where each managed item is a file).

### Fix 3: markers and ownership

For shared files, `blockinfile` and managed markers (`# BEGIN ANSIBLE MANAGED BLOCK`) identify what Ansible owns, so you can remove just that part. For resources with tags (cloud), tag everything Ansible creates (`managed_by: ansible`) and reconcile by listing tagged resources.

## Conflicts: two tasks, one resource

Two roles both want to set a file's mode, one to `0600` and one to `0644`:

```yaml
- file: {path: shared.conf, state: touch, mode: "0600", ...}   # team A
- file: {path: shared.conf, state: touch, mode: "0644", ...}   # team B
```

Run twice: `ok=2 changed=2` the **first and the second time**. Each run, task A changes the mode to 0600 and task B changes it back to 0644: **the playbook never converges.** Every run reports changes, check mode always shows drift, and a handler notified by either task fires every time. This is a bug only the second run can reveal, and the "run twice and expect `changed=0`" test catches it (Level 1 · 10).

Causes: duplicated ownership of a resource across roles (`/etc/ssh/sshd_config` managed by a baseline role and an app role), copy-pasted tasks, and variable defaults that differ by role. Cure: assign each resource to exactly one owner (a role), make others depend on it via variables, and use a drop-in directory so independent roles manage independent files.

## Drift: the world changes between runs

Drift sources: manual edits during incidents, other automation (package managers' post-install scripts, configuration agents), unattended upgrades, applications rewriting their configs, and tasks with unpinned versions (`state: latest`). Drift is *normal*; the goals are to detect it and decide.

- **Detect:** run the playbook in check mode on a schedule; the changed tasks are the drift report (Level 4 · 06 builds an auditor around this).
- **Classify:** a change reported on `app.conf` means someone edited it; a change reported on a task that touches `/etc/hosts` every run might be a conflict or a legitimately dynamic file.
- **Decide:** re-converge (apply), or accept the manual change by encoding it in the playbook.
- **Prevent:** limit who may log in and edit by hand, and when they do, require an incident ticket that ends in a pull request.

Enforcement frequency is a policy choice. Applying automatically every hour keeps machines honest and risks overwriting a deliberate emergency fix. Applying on demand allows drift to accumulate. Many teams run check mode continuously and apply only through a reviewed pipeline.

## Convergence properties to test

1. **Idempotent:** second run `changed=0`.
2. **Convergent from any starting state:** start from several states (empty, partially configured, wrongly configured) and check each ends at the same final state. The Level 1 project tested a drifted state.
3. **Order-independent where possible:** tasks managing different resources should not depend on each other's order; tasks that do depend on order should be in one role with a documented sequence.
4. **Reversible changes:** removing something from the playbook should be an explicit step (state absent), tested in a scenario "v1 then v2".
5. **No dependence on the previous run:** a clean machine and an old machine converge to the same result.

A good test for item 4 is exactly the experiment above: run v1, then v2, then assert the retired file is gone. The test fails until v2 contains the explicit removal or the purge.

## Modeling desired state when Ansible is not the source of truth

Where an external system owns the truth (a CMDB, Terraform state), generate the Ansible variables from it (dynamic inventory, Lesson 03), so playbooks consume state without storing it. That avoids a second source of truth.

## How It Actually Works

Each module is a function from (current state read from the target, requested arguments) to (actions, result). There is no memory between runs: the "state" is the host itself, read fresh. A removed task simply never executes, so its previous effects remain, and nothing in Ansible can tell which effects came from which version of the playbook. Convergence arises from every task being a pure "ensure X" operation; two tasks that ensure incompatible things about the same X make the system a fixed-point-free loop. The recap's `changed` count is the number of tasks whose modules found a difference, so a persistent non-zero count on an unchanged system is direct evidence of either non-idempotent tasks or conflicting owners.

## Common mistakes

- **Deleting a task and assuming the thing is gone.**
- **Purge patterns that match too much.**
- **Two roles owning one file.**
- **Ignoring a task that changes on every run** ("it's just noisy").
- **Auto-applying over a manual emergency fix.**
- **No scheduled drift detection.**
- **Treating `state: latest` as convergent.**

## Exercise

1. Reproduce v1 → v2 → v3 and write the pytest that asserts the retired file is removed after v3 but not after v2 (documenting the orphan).
2. Reproduce the flip-flop, then fix it so one task owns the file and the other consumes a variable. Prove `changed=0` on the second run.
3. Write a purge for a `conf.d`-style directory that refuses to run when the allow-list is empty and shows a count of files it would delete in check mode.
4. Design a drift-detection schedule for your environment: frequency, who reads the report, and the criteria for auto-apply.
