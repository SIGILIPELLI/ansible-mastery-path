---
title: "Ansible Cheat Sheet: Quick Reference, Beginner to Advanced"
description: "A free Ansible cheat sheet: 21 quick-reference tables from every level of the Ansible Mastery Path, each linked to its full lesson."
---

# Ansible Cheat Sheet

Quick-reference tables from **21 lessons** of the free Ansible Mastery Path, in course order from beginner to advanced. Each section links to the full lesson with explanations and runnable examples.

## Level 1 · Ansible Foundations

### [01 · What Ansible Is and How It Works](level-1/01-what-ansible-is.md)

*What you actually write*

| Piece | What it is | Lesson |
|---|---|---|
| **Inventory** | The hosts and groups you manage, and variables for them | 03 |
| **Playbook** | A YAML file: one or more **plays**, each mapping a set of hosts to a list of tasks | 04 |
| **Module** | The unit of work (`file`, `copy`, `template`, `user`, `package` ...) | 02 |
| **Task** | One module call with arguments, a name, and optional conditions | 04 |
| **Variables and facts** | Data from inventory, files, the command line, and information discovered on the host | 06 |
| **Handler** | A task that runs only when notified by a task that changed something | 08 |
| **Role** | A packaged directory structure of tasks, templates, defaults and handlers | Level 2 |
| **Collection** | A distribution unit for modules, roles and plugins (Galaxy) | Level 2 |
| **Vault** | Encryption for secret values in files | Level 2 |

### [02 · Ad-Hoc Commands, Modules and `ansible-doc`](level-1/02-adhoc-and-docs.md)

*Modules are the vocabulary*

| Area | Modules | Notes |
|---|---|---|
| Files | `file`, `copy`, `template`, `lineinfile`, `blockinfile`, `stat`, `fetch`, `unarchive` | `stat` reads state without changing it |
| Packages | `package`, `apt`, `dnf`, `pip` | Platform-specific; not run here |
| Services | `service`, `systemd` | Linux; not run here |
| Users | `user`, `group`, `authorized_key` | |
| Commands | `command`, `shell`, `script`, `raw` | Last resort; idempotency is on you |
| Control | `debug`, `assert`, `fail`, `set_fact`, `pause`, `wait_for` | Helpers inside playbooks |
| Info | `setup` (facts), `package_facts`, `service_facts` | |

### [03 · Inventory: Hosts, Groups and Variables](level-1/03-inventory.md)

*Host patterns*

| Pattern | Meaning | Matched |
|---|---|---|
| `web` | the group | web1, web2 |
| `web:db` | union | web1, web2, db1 |
| `prod:!db` | in prod but not db | web1, web2 |
| `web:&prod` | intersection | web1, web2 |
| `web1,db1` | explicit list | web1, db1 |
| `nomatch` | nothing | **0 hosts**, with a warning |

### [08 · Templates and Handlers](level-1/08-templates-handlers.md)

*Handlers*

| Run | What changed | Handler |
|---|---|---|
| 1 (fresh) | directory, site.conf, extra.conf (3 changes) | ran **once**, even though two tasks notified it |
| 2 (same inputs) | nothing | **did not run** (recap `changed=0`) |
| 3 (`upstreams` changed) | site.conf only | ran once |

### [09 · Debugging and Reading Failures](level-1/09-debugging-playbooks.md)

*Read the failure top-down*

| Symptom | Likely cause | First step |
|---|---|---|
| `YAML parsing failed ... did not find expected key` | Indentation, colon/quote problem | Look at the origin line and the one above |
| `'x' is undefined` | Missing variable, typo, wrong scope, fact not gathered | `debug: var=x`, check inventory with `ansible-inventory --host` |
| `couldn't resolve module/action` | Misspelled module or missing collection | `ansible-doc <name>`, check FQCN |
| `Unsupported parameters for module` | Wrong argument for this version | `ansible-doc -s <module>` |
| `Conditionals must have a boolean result` | String used as a boolean | Add `| bool` or fix the type |
| `UNREACHABLE` | Connection (SSH, host key, network, interpreter) | `-vvv`, try the same `ssh` command by hand |
| `FAILED` with `rc=...` and `stderr` | The command or module ran and failed | Read `stderr`/`msg`; reproduce by hand |
| `Missing sudo password` / `become` errors | Privilege escalation not configured | Test `sudo -n true` on the target |

### [10 · Project — A Verified Baseline Playbook](level-1/10-project-baseline-playbook.md)

*The test suite*

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

## Level 2 · Structure and Safety

### [02 · Variable Precedence, Measured](level-2/02-variable-precedence.md)

*The result (highest first)*

| Rank | Source | Notes |
|---|---|---|
| 1 | `-e` extra vars | beats everything, including `set_fact` |
| 2 | `set_fact` | |
| 3 | `include_vars` | |
| 4 | task `vars:` | |
| 5 | role `vars/main.yml` | |
| 6 | play `vars_files:` | |
| 7 | play `vars:` | |
| 8 | `host_vars/<host>.yml` | next to the inventory |
| 9 | inventory file, host entry | `h1 x=...` |
| 10 | `group_vars/web.yml` | specific group |
| 11 | `group_vars/all.yml` | |
| 12 | inventory file `[web:vars]` | |
| 13 | inventory file `[all:vars]` | |
| 14 | role `defaults/main.yml` | lowest |

### [03 · Jinja2 Filters and Expressions](level-2/03-jinja-filters.md)

*Lists of dictionaries*

| Expression | Result |
|---|---|
| `servers \| map(attribute='name') \| list` | `[a, b, c]` |
| `servers \| map(attribute='name') \| join(',')` | `a,b,c` |
| `servers \| selectattr('port', 'gt', 100) \| map(attribute='name') \| list` | `[b, c]` |
| `servers \| rejectattr('tags') \| map(attribute='name') \| list` | `[c]` (empty tag list is falsy) |
| `servers \| map(attribute='tags') \| flatten \| unique \| sort` | `[x, y]` |
| `dict(names \| zip(ports))` | `{a: 80, b: 8080, c: 443}` |

### [07 · Tags, Limits and Targeting](level-2/07-tags-limits.md)

*Tags: which tasks run*

| Command | Tasks that ran |
|---|---|
| (no options) | install, configure, always runs, untagged |
| `--tags configure` | configure, **always runs** |
| `--skip-tags setup` | always runs, untagged |
| `--tags debug_only` | always runs, **never unless asked** |
| `--tags nonexistent` | always runs |
| `--tags setup --skip-tags configure` | install, always runs |

### [08 · Delegation, Serial Batches and Strategies](level-2/08-delegation-strategies.md)

*Failure budgets*

| Setting | Failing hosts | Result |
|---|---|---|
| `serial: 1`, default (0%) | `n1` | `n1` failed; **`n2`..`n4` never ran** (the play aborted) |
| `serial: 2`, `max_fail_percentage: 50` | `n1` (1 of 2 = 50%) | batch continued; `n2` finished; **`n3` and `n4` ran** |
| `serial: 2`, `max_fail_percentage: 50` | `n1` and `n2` (100% > 50%) | play aborted; **`n3` and `n4` never ran** |

### [09 · Testing and Linting Ansible](level-2/09-testing-ansible.md)

*Rung 2: ansible-lint*

| Rule | Count | Meaning |
|---|---|---|
| `fqcn` | 4 | Use `ansible.builtin.shell`, not `shell` |
| `name` (missing/casing/play) | 4 | Name plays and tasks, start names uppercase |
| `no-changed-when` | 2 | `command`/`shell` without `changed_when` (breaks idempotency reporting, Level 1 · 05) |
| `no-free-form` | 2 | Avoid `copy: src=a dest=b` free-form arguments |
| `package-latest` | 1 | `state: latest` makes runs non-reproducible |

### [10 · Project — A Tested Role](level-2/10-project-tested-role.md)

*The tests*

| Test | Asserts |
|---|---|
| defaults and per-host override | `w1` file has `port=8080`; `w2`, with host var `webapp_port=9000`, has `port=9000` |
| role parameter overrides default | `vars: {webapp_workers: 7}` produces `workers=7` |
| idempotent | second run: exit 0 and `changed=0` for every host |
| handler fires only on change | first run: exactly one `RUNNING HANDLER`; second run: none |
| invalid port fails before changing anything | `webapp_port=70000`: non-zero exit, the message `webapp_port must be ...` appears, and the output directory does not exist |
| zero workers rejected | `webapp_workers=0`: non-zero exit |
| check mode writes nothing | `--check`: exit 0, output directory not created |
| role parameter beats `vars/main.yml` | passing `webapp_config_mode: "0600"` yields a file with mode `0600` |
| lint | `ansible-lint roles/webapp` exits 0 (production profile) |

## Level 3 · Extending Ansible

### [06 · Performance: Forks, Pipelining and Facts](level-3/06-performance.md)

*Forks: how many hosts run in parallel*

| `-f` | Wall time |
|---|---|
| 1 | 50.1 s |
| 5 | 11.1 s |
| 10 | 6.6 s |
| 20 | 4.5 s |

### [07 · Rolling Updates and Failure Budgets](level-3/07-rolling-updates.md)

*Results from the tests*

| Scenario | Outcome |
|---|---|
| All healthy | All eight at `2.0`, all in rotation, three batches ran, exit 0 |
| Canary (`n1`) fails smoke test | Exit non-zero; **all hosts at `1.0`** (the canary rolled back, nobody else touched); all in rotation; only one batch started; the canary's event log reads `drained`, `rolled back` |
| `n3` fails (second batch) | Exit non-zero; `n1` stays at `2.0` (first batch succeeded); `n3` back at `1.0`; `n6`, `n8` (third batch) still at `1.0`; all in rotation |
| Re-run after the fix | Finishes: all eight at `2.0` (hosts already updated are no-ops) |
| Run twice when healthy | Second run changes no versions |

### [10 · Project — A Tested Custom Module](level-3/10-project-custom-module.md)

*The 25 tests*

| Group | Count | Examples |
|---|---|---|
| Pure function | 11 | add, replace, unchanged returns same lines, remove, absent-when-missing no-op, comments preserved, duplicates collapsed, spaces around `=`, empty file, prefix key not confused, hash equals `hashlib` |
| Module as Ansible runs it | 13 | create-then-idempotent; check mode does not write; diff content; mode set; **mode-only change reported**; three rejected inputs (parametrised); missing file; absent on missing is a no-op; unknown argument rejected; `filehash` missing file and output |
| Real `ansible-playbook` | 1 | second run `changed=0` |

## Level 4 · Operating Ansible

### [01 · Controllers, AWX and Execution Environments](level-4/01-automation-platform.md)

*What a controller adds*

| Capability | What it means |
|---|---|
| **Projects** | A link to a Git repository with playbooks; the controller syncs it before jobs |
| **Inventories** | Static or dynamic sources, with credentials for cloud syncs |
| **Credentials** | Encrypted stores for SSH keys, vault passwords, cloud tokens; users can *use* a credential without *seeing* it |
| **Job templates** | A saved combination: playbook + inventory + credentials + limit + extra vars + execution environment |
| **RBAC** | Who can run, edit, or read each template, inventory and credential |
| **Scheduling** | Cron-like runs, for drift audits and maintenance (Lesson 06) |
| **Workflows** | Chains of templates with success/failure branches and approval steps |
| **Logging and history** | Every run's output, who started it, with what parameters; usually an API and a UI |
| **API / CLI** | Trigger jobs from CI or other systems |
| **Execution isolation** | Jobs run in separate containers (execution environments) rather than on a shared shell |

### [04 · Pull Mode and Bootstrap](level-4/04-pull-mode.md)

*`--only-if-changed` and drift*

| Situation | Command | Result |
|---|---|---|
| No new commit | `ansible-pull ... --only-if-changed` | `Repository has not changed, quitting`; **playbook not run** |
| New commit (`release` default changed 1 → 2) | with `--only-if-changed` | playbook ran, `changed=1`, motd now `version 2` |
| Someone edits motd by hand (`hacked`) | plain `ansible-pull` | playbook ran, `changed=1`, motd restored to `version 2` |
| Someone edits motd by hand | `--only-if-changed` | **nothing happened; the hand edit remained** |

### [05 · Terraform and Ansible Together](level-4/05-terraform-and-ansible.md)

*Division of labour*

| Concern | Better owned by | Why |
|---|---|---|
| Networks, VMs, load balancers, databases, DNS | Terraform | State, dependency graph, plan/diff, destroy |
| OS packages, config files, users, services on a host | Ansible | Fine-grained on-host modules, templates, handlers |
| Application deployment steps and orchestration | Ansible (or a deploy tool) | Ordering, batches, delegation |
| Bootstrapping (first boot) | cloud-init / images, then Ansible | The machine must exist and be reachable first |
| Secrets storage | A secret manager | Neither tool is a secret store |

### [06 · Auditing Drift with Check Mode](level-4/06-drift-audit.md)

*The runner and its exit codes*

| Exit | Meaning |
|---|---|
| 0 | No drift on any host |
| 1 | Drift found (at least one task would change something) |
| 2 | A task failed or a host was unreachable: **the audit result is not trustworthy** |

### [07 · Automation Incidents and Blast Radius](level-4/07-incidents.md)

*How playbooks cause incidents*

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

### [10 · Capstone — Managing a Simulated Fleet](level-4/10-capstone-fleet.md)

*The sequence, as tests*

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

---

Go deeper with the full [Ansible Mastery Path](index.md) curriculum or test yourself with the [interview questions](interview-questions.md).
