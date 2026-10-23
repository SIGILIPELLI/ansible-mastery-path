---
description: "Debugging playbooks: reading failures, verbosity, debug and assert, check mode, start-at-task pitfalls and what -vvv reveals, with real error output."
---

# 09 · Debugging and Reading Failures

Automation fails in boring ways: a typo, an undefined variable, a wrong assumption about the target. Learning to read Ansible's output quickly is a skill you build once. This lesson walks through the real failures hit while building this course and the tools used to diagnose them.

!!! note "What was run"
    All messages and counts are from real runs of ansible-core 2.21.5 on macOS with local connections. Error text changes between versions; the diagnosis technique does not. SSH-specific failures (permission denied, host key checking, unreachable) were not reproduced and are described from documentation.

## Read the failure top-down

Ansible's error format identifies the **task**, the **host**, the **module**, and (in recent versions) prints the **source location with a caret**. For an undefined variable:

```text
TASK [ansible.builtin.debug]
[ERROR]: Task failed: Finalization of task args for 'ansible.builtin.debug' failed:
Error while resolving value for 'msg': 'not_defined' is undefined

Origin: .../undef.yml:4:7
2   gather_facts: false
3   tasks:
4     - ansible.builtin.debug: {msg: "{{ not_defined }}"}
```

Read: *what* failed (resolving task arguments), *why* (`not_defined` is undefined), *where* (file:line:column). Most errors are one of these categories:

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

## Verbosity

```text
default : 20 lines for a 3-task playbook
-v      : 16 lines   (shows module return values for each task)
-vvv    : 106 lines  (shows connection and execution details)
```

Increase only as needed: `-v` shows results (stdout, rc, diff-like content); `-vv` shows task file locations and more; `-vvv` shows the connection method and the remote commands. In the `-vvv` output:

```text
<web1> ESTABLISH LOCAL CONNECTION FOR USER: bhanuja
<web1> EXEC /bin/sh -c 'echo ~bhanuja'
<web1> EXEC /bin/sh -c '( umask 77 && mkdir -p "` echo /Users/bhanuja/.ansible/tmp `" && mkdir ... )'
Using module file .../ansible/modules/file.py
```

That is Ansible creating a private temp directory (`umask 77`), choosing the module file and shipping it. On an SSH connection the same lines show the `ssh` command line with all options, which you can paste into a terminal to reproduce a connection problem. `-vvvv` adds connection-plugin debugging. Never paste `-vvv` logs publicly without scrubbing: they may include usernames, paths and sometimes arguments with secrets (use `no_log: true` on sensitive tasks).

## `debug`, `assert`, `fail`

- `ansible.builtin.debug: var=name` prints a variable's value (including type and structure). `msg:` prints a templated string. Set `verbosity: 2` on a debug task to print only when `-vv` is used, so you can leave diagnostics in.
- `ansible.builtin.assert` states expectations and fails with a clear message:

```yaml
- ansible.builtin.assert:
    that: ["http_port | int < 1024"]
    fail_msg: "http_port {{ http_port }} needs root"
```

Output: `fatal: [web1]: FAILED! => {"msg": "http_port 8081 needs root"}`. Assertions at the top of a play or role (required variables defined, inputs valid, target OS supported) turn confusing mid-run errors into clear early ones, like input validation.
- `ansible.builtin.fail: msg=...` with `when:` is the same idea for custom conditions.

## Targeting what you debug

- `--limit web1` runs on one host. `--tags`/`--skip-tags` (Level 2 · 07) select tasks.
- `--list-hosts` and `--list-tasks` show the plan without running anything.
- `--step` asks before each task (interactive).
- `--check --diff` previews changes (Lesson 05).
- `--start-at-task "name"` begins at a task. **Careful:** it skips all earlier tasks, including setup tasks that later ones need. While testing it, I ran the handler playbook with `--start-at-task "render config"` after deleting the sandbox directory; the first task (`ensure dir`) was skipped, so the template task failed (`failed=1` with `ok=0`) because the directory did not exist. Use it to resume a long play when you know earlier state exists, not to skip setup.
- `ansible-playbook -e 'debug_var=1'` style switches in your own playbooks are fine, but prefer `-v` levels.

## Debugging templates and Jinja2

To see what a template would produce without deploying, render it with the `template` module into a temporary path (`dest: /tmp/rendered`) and read it, or use `debug: msg="{{ lookup('ansible.builtin.template', 'x.j2') }}"`. Common template errors: a missing `endif`/`endfor` (Jinja reports the line), an undefined variable (use `default` or check), or whitespace changes (use `trim_blocks`/`lstrip_blocks` settings and `-` markers like `{%- if x -%}`).

## Failure handling you can see

Output markers: `ok`, `changed`, `skipping`, `failed` (task failed, host removed from the play), `unreachable` (connection failed), `rescued` (a `rescue` block recovered, Level 2 · 04), `ignored` (failure ignored with `ignore_errors`). The recap's counts tell you at a glance: `failed=1` means one task failed for that host; `ok=0 failed=1` (as above) means the very first executed task failed.

A failed host is removed from the rest of the play. Other hosts continue. The command exits with a non-zero status if any host failed or was unreachable, so CI sees red. A play with `hosts` matching nothing exits zero (Lesson 03).

## A debugging checklist

1. Re-read the error from the top; find the task, module, file and line.
2. Reproduce on one host: `--limit host -v`.
3. Print the inputs: `debug: var=...` right before the failing task, and `ansible-inventory --host host` for inventory variables.
4. Run the underlying command by hand on the target as the same user.
5. Check module docs for the exact argument names and types for your version.
6. Check recent changes with `git diff`; many failures follow the last edit.
7. Reduce the playbook to the smallest case that still fails.

## How It Actually Works

Errors surface at three stages. At **parse time** the YAML loader and the playbook compiler detect structural problems (bad indentation, unknown keywords on a play or task) before any host is contacted, which is why `--syntax-check` is cheap. At **templating time** per host, argument expressions are evaluated; undefined variables and type errors surface here, as a task failure for that host. At **execution time** the module runs on the target and returns JSON; module-level validation (unsupported or missing parameters) happens inside the module's argument spec check, and runtime problems come back as `failed: true` with `msg` and any `stderr`. The verbosity flags change only what the controller prints; they do not change what runs, except that `-vvv` makes the SSH layer print its commands.

## Common mistakes

- **Running at full verbosity first** and drowning in output.
- **Not limiting to a single host** while debugging.
- **`--start-at-task` skipping prerequisites.**
- **`ignore_errors` left on** while debugging, hiding the failing step.
- **Printing secrets** with `debug` or `-vvv` in shared logs.
- **Trusting a green run** that skipped everything because a `when` was always false.
- **Editing the playbook and the inventory at once**, so you don't know which change fixed it.

## Exercise

1. Make each of these errors on purpose and record the message: a bad indent, an undefined variable, a misspelled module name, a wrong module argument. Which are caught by `--syntax-check`?
2. Add an `assert` at the top of a play that checks three required variables are defined and the OS family is supported.
3. Run a failing playbook with `-v` and `-vvv`; list three facts you learn only from the higher level.
4. Write a one-page personal debugging checklist for your environment, including the exact SSH command you would use to test a connection by hand.
