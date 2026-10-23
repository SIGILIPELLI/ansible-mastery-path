---
description: "Automation incidents and blast radius: how playbooks cause outages, a tested preflight guard that found its own group-nesting bug, and incident runbooks."
---

# 07 · Automation Incidents and Blast Radius

Automation multiplies mistakes as well as effort. One wrong `hosts:` pattern or one bad variable can change every server in minutes. The goal of operating Ansible safely is to make the **blast radius** of any single run small, visible and deliberate, and to be ready when something goes wrong anyway.

!!! note "What was run"
    The `preflight.py` guard (9 tests) was run against small inventories using the real `ansible` and `ansible-inventory` commands; the first end-to-end test failed because of a bug in the guard itself (below). The incident runbooks are general practice, not drawn from a real incident, and have not been exercised. See the CI/CD course (Level 4 · 07) for pipeline incident handling.

## How playbooks cause incidents

| Cause | Example | Control |
|---|---|---|
| Wrong target | `hosts: all` in a play meant for staging; a `--limit` forgotten | Preflight, protected groups, inventory per environment |
| Wrong variable | `-e version=` empty; a default overridden by `-e` or `set_fact` (precedence, Level 2 · 02) | Input validation (`assert`), no free-text `-e` in templates |
| Non-idempotent task | A "fix" that restarts a service on every run | Idempotence test in CI (Lesson 02) |
| Batch too large | 200 hosts restarted at once | `serial`, failure budget, tested abort semantics (Level 3 · 07) |
| Conflicting owners | Two roles flip a setting each run (Level 3 · 08) | One owner per resource; audit |
| Drift repair that overwrote an emergency fix | Scheduled apply reverted a hot patch | Drift audit before apply; change freeze flags |
| Stale facts / cache | Acting on cached facts about a rebuilt host | Short fact cache expiry; gather before destructive tasks |
| Secret exposure | `debug` or `-vvv` log with a token | `no_log`, linter, log access control (Lesson 03) |
| Dependency drift | A collection or ansible-core upgrade changes behaviour (this course found `when:` on a string became an error in 2.21.5) | Pin versions; test upgrades; EEs |
| Inventory error | Dynamic source returns the wrong set or an empty set | Inventory sanity checks, fail on empty |
| Lack of rollback | A destructive task with no way back | Backups, `state: absent` as a deliberate step, rehearsed rollback |
| Credentials too powerful | The Ansible user can do anything everywhere | Least privilege, per-environment keys |

## A preflight guard: compute the blast radius first

`preflight.py inventory pattern [--max-hosts N] [--protected groups] [--allow-protected]` resolves the pattern to hosts using `ansible --list-hosts`, adds the group memberships from `ansible-inventory --list`, and refuses when:

- the pattern matches **no hosts** (so a typo in CI does not become a green no-op);
- the host count exceeds `--max-hosts` (default 5);
- any target is in a **protected group** (default `production`) and `--allow-protected` was not given.

Example output:

```text
targets: 1 host(s): w1
REFUSED: touches protected group(s): production (use --allow-protected)      exit 1
```

### The bug the tests found

My first version built group membership from each group's `hosts` list only. The end-to-end test used an inventory like:

```ini
[web]
w1
w2
[production:children]
web
```

`w1` is in `web`, and `web` is a child of `production`, so `w1` **is in production**, but `production` has no `hosts` list of its own. The guard allowed `w1` to be touched without `--allow-protected`: **a safety check that approved the very case it exists to stop**. The test (expecting exit 1 and the word "protected") failed with exit 0. I rewrote `groups_of` to include **all ancestor groups** via the `children` relationship (cycle-safe), and added tests: ancestors included, multi-level nesting (`leaf → mid → production`), and cyclic definitions. After the fix, all 9 tests passed.

Lessons: (1) a guard rail needs a negative test for *each way* to hit the thing it protects, including indirect ones; (2) inventory group nesting is common (`production:children`), so any tool that reasons about groups must resolve it transitively; (3) the cheapest time to find such a bug is before the first production run.

Wire the guard in front of risky runs: a `make deploy` target, a CI job, or a controller template pre-step. Pair it with `--check --diff` (Lesson 06) for the content of the change.

## Making the blast radius small

1. **Separate inventories per environment** with no shared groups across them, and different credentials. The protected-group mechanism helps, but it is a second line of defence.
2. **Default to limits.** A playbook run for production requires a `--limit` or a controller survey value; assert on `ansible_limit is defined` (Level 2 · 07).
3. **Batches and budgets** (Level 3 · 07) with `any_errors_fatal` on irreversible steps.
4. **Canary first**: a designated host or group gets every change first.
5. **Check mode before apply** with the diff attached for review.
6. **Rate limit changes**: `throttle`, `serial`, and a pause between batches for monitoring to react.
7. **Staged credentials**: the credential used by a CI job for staging cannot reach production.
8. **Break-glass and change freezes**: a switch (a file or flag the playbook checks via `assert`) that blocks scheduled applies during an incident or holiday freeze.
9. **Kill switch**: an obvious, documented way to stop a running rollout (cancel the job; the playbook structure must leave hosts in a safe state, Level 3 · 07's `always`).

## Detection

- Monitor the **effects** (error rate, latency, capacity) during and after rollouts; a change window without monitoring is a blind change.
- Alert on **unusual automation activity**: runs outside the schedule, runs against production by unusual users, a surge in `changed` counts (e.g., the drift report finds 80% of hosts drifted after a run: your own change did something unexpected).
- Keep **run logs** with who ran what, with which parameters and revision (a controller does this; for CI it is the pipeline history).

## Response runbook for a bad run

1. **Stop the run.** Cancel the job; if it is a rolling update with a serial batch, the playbook should stop after the current batch (confirm).
2. **Freeze automation**: disable schedules and other jobs that could compound the damage.
3. **Assess scope**: which hosts changed? Use the run log and a `--check --diff` against desired state to see differences; the drift audit tool (Lesson 06) helps compare reality to the intended state.
4. **Decide**: roll back (previous playbook revision, if the change is reversible and the rollback tested), roll forward (a fix), or repair manually on the most affected hosts.
5. **Execute** in small batches with verification; use the same guard rails you used to roll out.
6. **Communicate**: status, scope, next update time.
7. **Restore normal operations** only when the cause is understood and a test or guard prevents recurrence.
8. **Review** (blameless): why did the change pass review and CI? Which guard would have stopped it? Add it (a test, a lint rule, a preflight check) and record the action items with owners.

Everything in the CI/CD course's pipeline-incident runbooks (broken main, leaked secret, compromised build input) applies to the pipeline that runs Ansible; the Ansible-specific parts are the blast radius, the idempotence of repair and the verification of end state.

## Rehearse

Run a game day: pick a harmless change, run a "bad" playbook against a staging fleet (one that deletes a managed file everywhere), and practise detection, stopping, assessing with the drift audit, and repairing with a targeted `--limit` run. The capstone test (Lesson 10) does exactly this on twelve simulated nodes: audit finds three drifted nodes, repair touches only those three, and untouched nodes' files keep their modification times.

## How It Actually Works

`preflight.py` asks Ansible itself which hosts a pattern selects (`ansible PATTERN -i INV --list-hosts`), instead of reimplementing pattern evaluation, so it honours `!`, `&`, ranges and group nesting exactly as a real run would. It reads group structure from the JSON that `ansible-inventory --list` prints: each group object may have `hosts` and `children`. Resolving ancestors is a graph walk over the `children` edges from each host's direct groups upward, with a visited set so cycles terminate. Asking the real tool for the pattern and using the data only for membership is the design choice that keeps the guard small and correct.

## Common mistakes

- **Guards that don't resolve nested groups.**
- **Protected-group checks that can be turned off by default** (`--allow-protected` in scripts).
- **No limit on production templates.**
- **Rollback plans never rehearsed.**
- **Automation credentials shared across environments.**
- **Alerts that fire only on failure**, not on unexpected success at scale.
- **No freeze mechanism** for scheduled applies during incidents.

## Exercise

1. Run `pytest src/l4/test_preflight.py`; add a test for a pattern with an exclusion (`web:!w2`) and one for a range pattern.
2. Create an inventory with two overlapping environment groups and show a host that belongs to both; make the guard refuse it unless both are allowed.
3. Write a `freeze.yml` check (an `assert` against a file or variable) and show a scheduled run refusing to apply during a freeze.
4. Plan a game day for your own estate: the injected fault, the signals, who acts, and the success criteria.
