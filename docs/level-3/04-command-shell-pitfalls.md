---
description: "Command and shell without breaking idempotency: what each really does, pipefail, injection and quote, argv, creates and removes, changed_when, measured."
---

# 04 · `command` and `shell` Without Breaking Idempotency

Sometimes no module exists and you must run a command. `ansible.builtin.command` and `ansible.builtin.shell` are the escape hatches, and they are where most Ansible bugs come from: wrong quoting, hidden failures in pipes, injection from variables, and tasks that report `changed` forever. This lesson runs each hazard.

!!! note "What was run"
    All outputs come from `src/l3/cmd.yml` on macOS (zsh is the user's shell, but Ansible's `shell` module used `/bin/sh`, and `/bin/bash` where I set `executable`). Results of shell features can differ on Linux with `dash` as `/bin/sh`; test on your target.

## `command` versus `shell`

- `command` runs a program **without a shell**: no pipes, no redirection, no `&&`, no `$(...)`, no globbing.
- `shell` runs the line through a shell (`/bin/sh` by default), so all of those work, and so do their dangers.
- `raw` sends text over SSH without Python (for bootstrapping); `script` copies and runs a local script.

My experiment: `echo $HOME | wc -c`.

```text
command: stdout = "/Users/bhanuja | wc -c"      # $HOME was expanded; the pipe and wc were passed as literal arguments
shell:   stdout is a number (the character count)
```

Two surprises: first, `command` still **expanded `$HOME`** (it expands environment variables in arguments; I had assumed it did not), while the `|` became a plain argument to `echo`. Second, `$(basename $PWD)` earlier in Lesson 08 was **not** evaluated by `command`. Do not rely on partial shell behaviour; if you need shell syntax use `shell`, and if you do not, use `command` with the `argv` form.

## `argv`: no quoting problems

```yaml
- ansible.builtin.command:
    argv: [echo, "a b", "c;d"]
```

printed `a b c;d`: each list element is one argument, with no shell and no splitting. This is the safest form when arguments contain spaces or special characters, or come from variables.

## Injection through variables

```yaml
- ansible.builtin.shell: echo {{ evil }}
  vars: {evil: "ok; echo INJECTED"}
```

Output lines: `ok` and `INJECTED`. The variable's text was pasted into the shell line, so `; echo INJECTED` ran as a second command. In real life the variable comes from inventory, a facts value, a user-provided `-e`, or an API, and the injected command could be `rm -rf`. With the `quote` filter:

```yaml
- ansible.builtin.shell: echo {{ evil | quote }}
```

the output was one line, `ok; echo INJECTED`, treated as data. **Rule: every variable interpolated into `shell:` must go through `| quote`**, or use `command` with `argv`, or pass data through environment variables (`environment: {NAME: "{{ value }}"}` and `"$NAME"` in the script). The CI/CD course's script-injection lesson (Level 2 · 10 there) is the same bug in another place.

## Pipes hide failures

```yaml
- ansible.builtin.shell: false | cat
```

Result: `rc=0`. The pipeline's status is the status of the **last** command, so the failing `false` was invisible. With bash and `pipefail`:

```yaml
- ansible.builtin.shell: set -o pipefail; false | cat
  args: {executable: /bin/bash}
```

`rc=1`. Always set `executable: /bin/bash` and `set -o pipefail` for pipelines you depend on (`ansible-lint` has a rule for this, `risky-shell-pipe`). `/bin/sh` may be `dash`, which lacks `pipefail`.

## Making commands idempotent

1. **Use a module** instead (`file` rather than `mkdir`, `get_url` rather than `curl`, `lineinfile` rather than `echo >>`). Check `ansible-doc -l | grep` and collections first.
2. **`creates` / `removes`:** skip the command if a path exists / does not exist.

```text
touch made with creates -> changed=True  (file did not exist)
rm made  with removes   -> changed=True  (file existed)
```

Both fired in my run because the sequence creates and then removes the same file, so **every run created and removed it again**: a good reminder that `creates`/`removes` look at a file, not at the intent, and combined carelessly they make a task pair that flips on each run (Lesson 08).
3. **Check first, act second:** `stat` (or a read-only command) registers the state; the action task has `when:`.
4. **`changed_when`:** derive `changed` from the output. A script printing `created` or `unchanged`:

```yaml
- ansible.builtin.shell: "test -f flag && echo unchanged || { touch flag; echo created; }"
  register: ch
  changed_when: "'created' in ch.stdout"
```

First run `changed=True`, second run `changed=False` (measured). Use `changed_when: false` for read-only commands.
5. **`failed_when`** for tools whose exit codes mean something else (grep returns 1 for "no match").
6. **Make the command itself idempotent** (`mkdir -p`, `ln -sfn`, `useradd` guarded by `id`), and still add `changed_when`.

## Environment, working directory, and privilege

- `chdir:` sets the working directory; `environment:` sets variables; `args: {executable: ...}` picks the shell.
- `become` applies to the command like any task.
- `command` runs with a minimal environment; `PATH` may not include what your interactive shell has. Use absolute paths or set `environment: {PATH: ...}`.
- Output is captured in `stdout`/`stderr` and printed in logs; do not echo secrets (`no_log`).

## Check mode

`command` and `shell` are **skipped** in check mode (unless `check_mode: false` on the task), so tasks after them may not see their output. For a read-only command whose output later tasks need, set `check_mode: false` and `changed_when: false`. For commands that change things, you can pair with `creates`/`removes`, which Ansible can evaluate in check mode.

## A pre-flight review checklist for every `shell:`

1. Is there a module that does this?
2. Does it need shell features? If not, use `command` + `argv`.
3. Is every interpolated variable quoted?
4. If it has a pipe, is `pipefail` on and bash selected?
5. How does it report `changed`? Is it guarded by `creates`, `removes`, `when` or `changed_when`?
6. What does it do when run twice? When run in check mode?
7. Does it print or leak secrets?

## How It Actually Works

The `command` module splits its argument string with `shlex`-like rules into an argument vector and calls `module.run_command` which executes it with `subprocess` (no shell), after applying `os.path.expandvars`-style expansion to the arguments, which is consistent with `$HOME` being replaced. `shell` calls the same helper with `use_unsafe_shell=True`, which hands the string to `/bin/sh -c` (or `executable`), so the shell interprets everything. Both return `rc`, `stdout`, `stderr` and always set `changed: true`, because the module has no idea what the command did, unless `creates`/`removes` short-circuits it before running. That is the whole story behind "command is never idempotent": idempotency has to be supplied by you (guards or `changed_when`), not by the module.

## Common mistakes

- **Unquoted variables in `shell`.**
- **Pipelines without `pipefail`.**
- **`changed_when: false` on a command that changes something.**
- **`command` with shell syntax**, half working.
- **Relying on a login shell's PATH.**
- **Commands that print secrets.**
- **A `creates` path that is never created**, so the command re-runs forever.

## Exercise

1. Run `src/l3/cmd.yml`. Which task in it changes state on every run? Fix the pair so both runs report `changed=0` on the second run.
2. Write a `shell` task with a pipeline and prove with a failing first command that `pipefail` changes the result.
3. Convert three `shell:` tasks from a playbook of your own to modules or `command` + `argv`, and say what you gained.
4. Write the injection test: a variable containing `; touch /tmp/pwned` run through `shell` with and without `quote`, and verify the file is created only in the unsafe case.
