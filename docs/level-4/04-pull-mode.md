---
description: "Pull mode with ansible-pull: run from Git on the node, only-if-changed semantics, drift repair, a measured gotcha, and bootstrap patterns for new machines."
---

# 04 · Pull Mode and Bootstrap

Normally a control node pushes to many hosts. With **`ansible-pull`** the host pulls its own configuration from a Git repository and applies it to itself. Pull mode scales to large fleets without a central controller, handles machines that cannot be reached from outside (laptops, edge devices, autoscaled instances behind NAT), and repairs drift automatically when scheduled.

!!! note "What was run"
    Real runs of `ansible-pull` (ansible-core 2.21.5) against a local Git repository (`file:///tmp/pullrepo`) on a Mac, applying a playbook to `localhost`. A scheduler (cron, a systemd timer) and real remote machines were **not** involved; that part is described.

## How it works, shown

A tiny repository with `local.yml`:

```yaml
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: managed file
      ansible.builtin.copy:
        dest: /tmp/pullout/motd
        content: "version {{ release | default('1') }}\n"
        mode: "0644"
```

```text
$ ansible-pull -U file:///tmp/pullrepo -d /tmp/pullwork -i localhost, local.yml
Starting Ansible Pull at ...      -> clones the repo, runs local.yml:  ok=1 changed=1     (motd: "version 1")
$ (same command again)             -> repository unchanged; playbook runs again:  ok=1 changed=0
```

Options used: `-U` repository URL, `-d` working directory for the checkout, `-i localhost,` an inventory containing just the local host (the trailing comma makes it a literal host list). By default `ansible-pull` looks for a playbook named after the host (`<hostname>.yml`) or `local.yml`; here I named it explicitly. The first run **cloned** the repository into `-d`, subsequent runs **updated** it with a fetch, then ran the playbook.

## `--only-if-changed` and drift

`--only-if-changed` (`-o`) skips the playbook if the repository has not changed since the last pull. My measurements:

| Situation | Command | Result |
|---|---|---|
| No new commit | `ansible-pull ... --only-if-changed` | `Repository has not changed, quitting`; **playbook not run** |
| New commit (`release` default changed 1 → 2) | with `--only-if-changed` | playbook ran, `changed=1`, motd now `version 2` |
| Someone edits motd by hand (`hacked`) | plain `ansible-pull` | playbook ran, `changed=1`, motd restored to `version 2` |
| Someone edits motd by hand | `--only-if-changed` | **nothing happened; the hand edit remained** |

The last row is the important gotcha: `--only-if-changed` is an optimisation for "apply when the code changes", and it **does not repair drift**, because drift is a difference between the host and the repo, and the repo did not change. For drift repair you must run the playbook on every pull (no `-o`), or run it on a schedule with a periodic forced apply (for example every pull without `-o`, but pulling rarely).

## Scheduling

`ansible-pull` is meant to run from a scheduler on each node: a cron entry such as every 15 minutes, a systemd timer, or a configuration agent. Considerations (described, not run here):

- **Splay**: add random delay (`--sleep N` randomises up to N seconds) so hundreds of nodes do not hit the Git server at the same moment.
- **Locking**: prevent overlapping runs (use `flock` or a systemd unit that won't start twice).
- **Logging**: capture output to syslog/journal and ship it; there is no central controller log by default.
- **Reporting**: pull mode has no built-in central view; send a heartbeat or run result to a monitoring system (for example write a metrics file or post to an endpoint at the end of the playbook), and alert on nodes that haven't reported.
- **Failures**: a broken commit on the main branch will run on every node. Roll out from a branch/tag per ring (canary nodes track `canary`, the rest `stable`) and pin the checkout with `-C <ref>` (`--checkout`).
- **Security**: the node needs read access to the repository (a deploy key or token with read-only scope; keep it away from the playbook's own secrets) and should verify what it runs. `ansible-pull` supports `--verify-commit` to require signed commits (not run here). Secrets in the repo must be vaulted, and each node needs the vault password somehow (a file placed at bootstrap, or fetched from a secret manager with the node's identity).

## Push versus pull

| | Push (`ansible-playbook` from a controller) | Pull (`ansible-pull` on each node) |
|---|---|---|
| Who initiates | Operator or CI | The node, on a schedule |
| Reachability | Controller must reach nodes (SSH, WinRM) | Node must reach Git |
| Scale | Bounded by controller and forks | Scales with nodes; Git server load |
| Orchestration (ordering across hosts, rolling batches) | Natural (`serial`, `delegate_to`) | Poor: nodes act independently |
| Drift repair | Only when you run it | Automatic if scheduled and run without `-o` |
| Visibility | Central output | You must build reporting |
| Credentials | Controller holds access to all nodes | Each node has only its own access |
| Fast response | Immediate | Up to one interval |

Choose pull for large, loosely coupled or hard-to-reach fleets where each node's configuration is independent; push for coordinated changes (rolling updates across a cluster, database failover). They combine: pull for the baseline on every node, push for orchestrated operations.

## Bootstrap patterns

A new machine needs Ansible and a first run. Patterns:

1. **Image bake**: build the OS image with Ansible (baseline role) once, with Packer or similar; machines boot already configured, and pull mode maintains them.
2. **cloud-init / user-data**: a small script installs Python and Ansible and runs `ansible-pull` once, which then installs the scheduler (so the machine keeps itself updated). A common sequence: install packages, `ansible-pull` the `bootstrap` playbook, which configures the cron/timer.
3. **Provisioning tool**: Terraform creates instances and triggers a push run (Lesson 05).
4. **Manual seed** for a handful of special machines: run `ansible-pull` by hand.

The bootstrap playbook should itself be idempotent and small: install the dependencies, place credentials (for example a read-only Git deploy key delivered through the cloud's metadata or a secret service, not stored in the repository), and install the periodic job. Keep it separate from the full configuration so you can reason about the trust chain: the first run determines what the machine will trust afterwards.

## Pitfalls

- **A single broken commit** affects every node within one interval. Protect the branch, require review and CI (Lesson 02), and use rings.
- **Time skew and partial runs**: nodes converge at different times, so versions differ during a rollout; design changes to be backward compatible.
- **Inventory**: with `-i localhost,` playbooks cannot see other hosts; anything needing `groups` or `hostvars` of other nodes does not work as in push mode.
- **Roles from Galaxy** are fetched at run time unless vendored (needs network access and trust), and collection dependencies must be installed on each node (an EE is not used).
- **Unattended breakage** is more serious than in push: no one is watching. Use `any_errors_fatal`-style guard rails, health checks and automatic rollback tags where possible.

## How It Actually Works

`ansible-pull` is a small program that first runs the `git` module (via an ad-hoc call to `ansible`) against `localhost` to clone or update the repository, and records whether the repository changed (`before` and `after` commit IDs, which you can see in the quit message). Then, unless `-o` applies, it runs `ansible-playbook` on the playbook path inside the checkout with the supplied inventory. Because the second step is just a normal playbook run, everything about idempotency, check mode and variables is unchanged. The `--only-if-changed` logic compares only the repository's commit IDs, which explains why local drift is invisible to it.

## Common mistakes

- **Using `-o` and expecting drift repair.**
- **No splay**, creating thundering herds on the Git server.
- **No reporting**, so silent failures persist for weeks.
- **All nodes tracking `main`** with no rings.
- **Storing the deploy key or vault password in the repository.**
- **Playbooks that assume other hosts are visible.**
- **No lock**, so slow runs overlap.

## Exercise

1. Reproduce the four-row table with a local repo. Then add `--verify-commit` handling in your design notes (what would you need to set up?).
2. Write a `bootstrap.yml` that installs a cron entry (as a file in a sandbox directory) running `ansible-pull` with a splay, and test it for idempotency.
3. Design the ring rollout for 1,000 nodes: canary tag, soak time, promotion, and how you stop a bad release.
4. Add a heartbeat task at the end of a playbook that writes a timestamp and result to a file; write a check that finds nodes whose heartbeat is older than two intervals.
