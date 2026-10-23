---
description: "Idempotency measured: ok versus changed on repeat runs, command and creates, check and diff mode, and drift detection, from real ansible-playbook runs."
---

# 05 · Idempotency, `changed` and Check Mode

The promise of configuration management is **convergence**: no matter what state a machine starts in, running the playbook brings it to the desired state, and running it again changes nothing. This lesson measures that promise on real runs, shows where it breaks, and explains how check mode and diff mode let you see changes before making them.

!!! note "What was run"
    Real `ansible-playbook` (ansible-core 2.21.5) runs on a Mac with `ansible_connection=local`, so the modules edited files and directories in a sandbox. Package, service and user modules were not run. The recaps and diff output shown are copied from those runs.

## First run, second run

A four-task playbook: create a directory with a mode, write a config file, run `echo hi` with `command`, and run `touch marker` with `command` guarded by `creates:`.

```text
First run                                    Second run
make dir ........... changed                 make dir ........... ok
write config ....... changed                 write config ....... ok
raw command ........ changed                 raw command ........ changed   <-- still changed
command + creates .. changed                 command + creates .. ok

recap: ok=4 changed=4                        recap: ok=4 changed=1
```

Three kinds of behaviour:

1. **State-aware modules** (`file`, `copy`) compare the current state with the request. Second run: `ok`. That is idempotency.
2. **`command`/`shell` with no guard** cannot know; it reports `changed` every time. A pipeline that checks "no changes on the second run" will fail forever on it.
3. **`command` with `creates:`** is made idempotent by a condition: if the file exists the command is skipped and reported `ok`. `removes:` is the mirror image. These two arguments are the cheapest way to make a command idempotent when no module exists.

The recap line is the instrument: the number of `changed` tasks on a repeat run should be **zero** for a converged system. A Level 1 project (Lesson 10) turns that into an automated test.

## `changed_when` and `failed_when`

For commands you cannot avoid, tell Ansible how to interpret the result:

```yaml
- name: query version (read only)
  ansible.builtin.command: myapp --version
  register: ver
  changed_when: false          # reading never changes anything

- name: apply migration
  ansible.builtin.command: myapp migrate
  register: mig
  changed_when: "'applied' in mig.stdout"
  failed_when: mig.rc not in [0, 3]
```

`changed_when: false` is the single most common fix for a noisy playbook. `changed_when` with a stdout test gives truthful reporting when the tool prints something distinct. Do not use `changed_when: false` on a task that really changes state; you would blind check mode and drift reports (Level 4 · 06).

## Check mode: "what would you do?"

`--check` runs the playbook in a dry-run mode where modules that support it report what they would change. After the baseline was applied, a stray line appended to the config file and the playbook was run with `--check --diff`:

```text
TASK [write config]
--- before: /tmp/demo/app.conf
+++ after: /tmp/demo/app.conf
@@ -1 +1 @@
-port=9999
+port=8080
changed: [localhost]
TASK [raw command (always changed)]
skipping: [localhost]
```

Observations from real runs:

- The diff shows exactly the drift: someone had set `port=9999`; the playbook would restore `8080`.
- The file was **not** modified: afterwards `cat app.conf` still showed `port=9999`.
- The `command` task was **skipped**, because command modules cannot predict their effect. In check mode their results are unknown, so tasks that depend on their registered output may behave differently or fail. Add `check_mode: false` to a read-only command whose output later tasks need (it will run for real, so it must be safe), or `check_mode: true` to force dry-run behaviour.
- A task that `notify`s a handler *reports changed in check mode*, and the handler is also simulated, so a check run is a good preview of what would restart.

Check mode is reliable only for modules that implement it faithfully. For `file`, `copy`, `template`, `lineinfile`, `blockinfile` and similar, it is good. For modules that depend on earlier tasks' real effects, a check run may be misleading: a task that would only work after a package is installed may fail or report wrong results in check mode because the package was not actually installed. Treat "no changes in check mode" as strong evidence, and "changes in check mode" as a list to read.

## Diff mode

`--diff` prints before/after for file-content modules (`template`, `copy`, `lineinfile`, `blockinfile`). It can be used without `--check` to log what actually changed. **Warning:** diffs print file content into logs. Files that contain secrets must be protected with `no_log: true` or `diff: false` on that task.

## Idempotency is a design habit, not a switch

- Prefer a module to a command; prefer `state:` arguments (`present`, `absent`, `latest`, `started`).
- Make operations safe to repeat: `lineinfile` with a `regexp` replaces a line instead of appending a duplicate each run; `blockinfile` manages a marked block; `file: state=directory` instead of `mkdir`.
- Avoid `state: latest` for packages in production runs unless you want upgrades whenever someone runs the playbook.
- Avoid tasks that depend on the current time or random values in their arguments (a timestamp in a file makes every run `changed`).
- Verify by running twice. If the second run reports changes, fix it before shipping.

## Why "idempotent" is subtler than "no changes"

A playbook can report zero changes and still be wrong (it checks the wrong thing), or report changes every run and be harmless (a command that restarts nothing). The aim is: **`changed` means something really changed, and `ok` means the system already matched.** Honest reporting is what makes check mode, drift audits and CI gates trustworthy.

## How It Actually Works

Each module implements its own comparison. `file` calls `stat` on the path and compares owner, group and mode with the requested values; `copy` computes a checksum of the destination and compares it with the checksum of the source content; `template` renders the Jinja2 text on the controller, then behaves as `copy`. If the comparison shows a difference, the module applies the change and returns `changed: true`; otherwise it returns `changed: false` without touching the target. In check mode the module is instructed (via an argument in its input JSON) not to write, and it returns what it would have done. The `command` module has no way to inspect the effects of an arbitrary command, so it returns `changed: true` unless `creates`, `removes`, `changed_when` or check mode says otherwise. The `PLAY RECAP` counts come directly from these `changed` flags.

## Common mistakes

- **Never running twice** to verify idempotency.
- **`command`/`shell` that changes state** with no `creates`/`removes`/`changed_when`.
- **`changed_when: false` on a real change**, blinding drift reports.
- **Trusting check mode** for tasks that depend on earlier tasks' real effects.
- **Timestamps or random values** in managed content.
- **Appending lines with `shell: echo >> file`** instead of `lineinfile`.
- **Printing secret content** through `--diff` into CI logs.

## Exercise

1. Reproduce the four-task playbook and its two runs. Add a fifth task using `shell: date > /tmp/x` and watch it change every time; then fix it two different ways.
2. Change a managed file by hand, run `--check --diff`, confirm the diff and that the file is untouched, then run for real.
3. Write a `command` task that is only ever `changed` when its output says so, using `changed_when`.
4. Explain why a play with `changed=0` on the second run is evidence of idempotency but not proof of correctness.
