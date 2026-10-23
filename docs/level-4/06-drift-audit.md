---
description: "Auditing drift with check mode: a callback plugin that writes JSON, a driftaudit tool with exit codes 0, 1 and 2, tested on a drifted fleet."
---

# 06 · Auditing Drift with Check Mode

Level 3 explained drift: the difference between what your automation says and what a machine actually has. Check mode (`--check --diff`) makes Ansible report those differences without changing anything, so a scheduled check run is an audit. This lesson builds a small auditing tool around it and measures what it can and cannot see.

!!! note "What was run"
    `src/l4/callback_plugins/driftreport.py` (a custom callback plugin) and `src/l4/audit/driftaudit.py` (a runner and summariser) were written and run against the Level 1 baseline on two simulated servers, and 9 pytest tests passed on the first run. Everything was local-connection with file-based "servers"; real services, packages and remote hosts were not audited.

## Why not parse the console output?

The screen output is for humans: it mixes task headers, item lines, diffs and warnings. On this install `ansible-doc -t callback -l` listed only `default`, `junit`, `minimal`, `oneline` and `tree`: setting `ANSIBLE_STDOUT_CALLBACK=json` failed with `Could not load 'json' callback plugin` (a JSON callback lives in a separate collection, `ansible.posix`, which I did not install), and `junit` needs an extra Python library. A callback plugin is a few dozen lines and gives exactly the data needed.

## The callback plugin

A callback plugin receives events as the run proceeds. The aggregate plugin `driftreport`:

```python
class CallbackModule(CallbackBase):
    CALLBACK_TYPE = "aggregate"; CALLBACK_NEEDS_ENABLED = True
    def v2_runner_on_ok(self, result):           # record only results with changed: true
    def v2_runner_on_failed(self, result, ignore_errors=False): ...
    def v2_runner_on_unreachable(self, result): ...
    def v2_playbook_on_stats(self, stats):       # at the end: write the JSON report
```

It must be enabled (`ANSIBLE_CALLBACKS_ENABLED=driftreport`) and found (`ANSIBLE_CALLBACK_PLUGINS=<dir>`). For each changed result it stores host, task name, the diff (when the module supplied one), and, for looped tasks, the **labels of the items that changed**. At the end it writes `report.json` with per-host summaries, the list of findings, `drifted_hosts` and `failed_hosts`.

## The runner and its exit codes

`driftaudit.py playbook inventory [args]` runs the playbook with `--check --diff` and the plugin enabled, reads the report, prints a summary and exits:

| Exit | Meaning |
|---|---|
| 0 | No drift on any host |
| 1 | Drift found (at least one task would change something) |
| 2 | A task failed or a host was unreachable: **the audit result is not trustworthy** |

The third code matters. A failed task in an audit may hide drift behind it, and an unreachable host was not audited at all. A cron job that treats "non-zero" as "drift" would miss those; reporting them separately lets you alert differently.

## What it found, for real

On the two-node baseline after a clean converge: `hosts audited: 2 drifted: 0 failed: 0`, exit 0. Then I vandalised the sandbox: appended a line to `node2`'s `app.conf`, set its `var/lib/app` directory to 777, and deleted `node1`'s `motd`. The audit printed:

```text
hosts audited: 2  drifted: 2  failed: 0
- node1
    [changed] message of the day
- node2
    [changed] directory tree items=['var/lib/app']
    [changed] app configuration
    [changed] restart app
```

exit 1. Note three things: the looped task reports **which item** drifted (`var/lib/app`, not all three directories); the handler `restart app` appears because the config change would notify it, so the report previews the restart; and nothing was repaired (a test confirms a hand-edited file is left as it was).

The nine tests: clean fleet exits 0; drift found per host with exit 1; the audit does not repair; diff text is captured (`PermitRootLogin yes` and `no` both present); looped items are identified; an undefined variable gives exit 2; a first run on an empty machine is "all drift"; and two for the summary formatter.

## Interpreting results

- **A change on a run you expected clean** could be: a manual edit (true drift), a non-idempotent task (always changes; fix the playbook), a conflict between two roles (Level 3 · 08), or a time-dependent value. Run the idempotence test first (Lesson 02); an audit on a playbook that fails it is noise.
- **Group by task name across hosts.** If the same task shows on 80% of hosts, it is probably the playbook, not 80 people editing files.
- **Distinguish expected variation** (a per-host cache file) and exclude it from management, rather than filtering the report.
- **The diff is evidence.** It shows what differs; it may contain secrets, so protect the report as you would the files (`diff: false` or `no_log` on sensitive tasks, and access control on stored reports).

## Blind spots of check mode (measured or known)

1. **`command` and `shell` are skipped** in check mode (Level 1 · 05), so they contribute no drift information. Replace with modules or add `check_mode: false` for read-only probes.
2. **Dependent tasks**: a task that depends on a previous task's real effects may report misleadingly (a service start that would only succeed after a package install). Package/service modules usually handle this with care but not always.
3. **Things the playbook does not manage** are invisible. An audit tells you whether managed resources match, not whether the machine has an unmanaged cron job or an extra user. Add `find`/`stat` based "unexpected item" checks (the purge pattern in check mode from Level 3 · 08) and security scanners.
4. **Failed hosts** are not audited (the exit 2 case).
5. **Modules with imperfect check support** may under-report. Test: for each module you rely on, change the thing by hand and confirm check mode notices.
6. **Time**: the audit is a snapshot; drift can occur a minute later.
7. **Handlers in check mode** are simulated; the report shows them as changes because they would run.

## Running audits

- **Schedule** nightly or weekly in CI or on a controller with read-only credentials where possible (check mode still needs the access to read state, and `become` for privileged files).
- **Store reports** with timestamps; trend the count of drifted hosts and tasks.
- **Alert** on exit 2 immediately (audit blind) and on exit 1 according to severity (changes to `sshd_config` and `sudoers` matter more than a log level).
- **Respond**: re-converge (apply), or investigate the manual change. For compliance-sensitive settings, make an incident out of it.
- **Close the loop**: for each drift cause found, decide a prevention (fewer people with shell access, a pipeline-only change policy).

A pipeline for the audit can reuse `ci.sh`'s check-mode step as a gate (Lesson 02), but the audit's value is in the report and trend, not just the exit code.

## How It Actually Works

Check mode is a flag (`_ansible_check_mode`) passed to each module in its arguments; modules that support it compute their result and skip the write, setting `changed` accordingly. The task executor passes each module result to the registered callbacks; `v2_runner_on_ok` fires for results that did not fail, with the full result dictionary including `changed` and (in diff mode) `diff`. The aggregate plugin accumulates findings in memory, so in one run on a big fleet the report grows with the number of changes and diff sizes. At `v2_playbook_on_stats` the stats object provides per-host summaries (`ok`, `changed`, `failures`, `unreachable`, `skipped`, `rescued`, `ignored`) used to compute `failed_hosts`. The wrapper is a normal subprocess run with environment variables enabling the plugin, which keeps the audit logic out of the playbook.

## Common mistakes

- **Auditing a non-idempotent playbook**, producing permanent noise.
- **Treating exit 2 as drift** (or ignoring it).
- **Auto-repairing** on every audit without review.
- **Believing a clean audit means a clean machine.**
- **Storing diffs with secrets** in plain reports.
- **Not testing check-mode support** of the modules you rely on.
- **Never alerting on unreachable hosts.**

## Exercise

1. Run `driftaudit.py` against a playbook of yours (use `--limit` for one host first) and categorise each finding: manual change, playbook bug, or expected.
2. For three modules you use, change the managed state by hand and confirm check mode reports it.
3. Extend the plugin to include the task's file and line (`result._task.get_path()`), and update the summary.
4. Write the alert policy: which findings page someone, which open a ticket, which are logged.
