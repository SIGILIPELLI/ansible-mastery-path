---
description: "Blocks, rescue and always, failed_when, ignore_errors, any_errors_fatal and force_handlers, run to show exactly what continues after a failure."
---

# 04 · Blocks, Errors and Rescue

By default, when a task fails on a host, Ansible stops running that host's remaining tasks and moves on with the others. That default is right most of the time, but real automation needs finer control: roll back a partial change, clean up in all cases, treat some non-zero exit codes as success, or stop the entire run if any host fails.

!!! note "What was run"
    All outputs are from a real run of `src/l2/blocks.yml` on ansible-core 2.21.5, localhost. Behaviours involving several hosts (`any_errors_fatal`, `max_fail_percentage`) were measured in Lesson 08 with `serial`.

## Blocks group tasks

A `block` groups tasks so you can apply keywords once (`when`, `become`, `tags`, `vars`, `ignore_errors`) and attach error handling:

```yaml
- name: deploy with rollback
  block:
    - ansible.builtin.debug: {msg: "1 apply new config"}
    - name: 2 health check (fails)
      ansible.builtin.command: /usr/bin/false
    - ansible.builtin.debug: {msg: "3 never reached"}
  rescue:
    - ansible.builtin.debug: {msg: "R rollback; failed task was '{{ ansible_failed_task.name }}' rc={{ ansible_failed_result.rc }}"}
  always:
    - ansible.builtin.debug: {msg: "A always: cleanup"}
- ansible.builtin.debug: {msg: "play continues after rescue"}
```

Actual sequence printed: `1 apply new config`, then the failure of `2 health check (fails)`, then `R rollback; failed task was '2 health check (fails)' rc=1`, then `A always: cleanup`, then `play continues after rescue`. Task 3 never ran. The recap said `rescued=1`, `failed=0`.

How it works: if any task in `block` fails, the remaining block tasks are skipped and `rescue` runs, where the special variables `ansible_failed_task` and `ansible_failed_result` describe what went wrong. If `rescue` completes successfully, the host is **considered recovered**: the play carries on and the host is not counted as failed. `always` runs whether or not the block failed. This is Ansible's try / except / finally.

**Rescue is not magic rollback.** It runs the tasks you wrote. A rollback task must itself be idempotent and safe to run when the failure happened at any point in the block (including before anything changed). Typical rescue content: restore a backup, flip a load balancer back, send an alert, then optionally `fail` so the run still reports failure.

A failing `rescue` task fails the host, and the `always` section still runs. In the experiment, a block whose rescue raised `fail: second` was marked with `ignore_errors: true` on the block, and the recap showed `ignored=1` while the play continued.

## Failing on purpose, and telling the truth about success

- `ansible.builtin.fail: msg=...` stops a host with a message (usually with `when:`).
- `ansible.builtin.assert` states several expectations and fails with `fail_msg` (Level 1 · 09).
- `failed_when:` redefines failure for a task. Many tools use non-zero exit codes for non-error states:

```yaml
- name: grep-like command
  ansible.builtin.command: sh -c 'echo warn >&2; exit 3'
  register: r
  failed_when: r.rc not in [0, 3]
  changed_when: false
```

With `rc=3` the task passed, and the next task could read `stderr=warn`. `failed_when: false` means "never fail; I'll inspect the result" (and is clearer than `ignore_errors` because it states intent and leaves genuine unreachable errors visible).

- `ignore_errors: true` continues after a failure *of this task* but still reports the failure in output (`...ignoring`) and counts `ignored` in the recap. It does **not** ignore unreachable hosts, and a failure inside a module's argument templating (like the undefined-variable error in Level 1 · 09) also counts as a failure that is then ignored, which can hide typos. Use it sparingly.
- `ignore_unreachable: true` is the separate switch for unreachable hosts.

## What happens to the rest of the play

Per host, the default: first failure removes that host from the rest of the play. In check mode the same. Two keywords change that:

- `any_errors_fatal: true` (on the play or a block): if **any** host fails the task, the whole play stops for **all** hosts. Good for steps where partial application is dangerous (a schema migration that must succeed everywhere or nowhere).
- `max_fail_percentage` with `serial` (Lesson 08): tolerates failures up to a limit within each batch.

Handlers do not run after a failure unless `force_handlers: true` (Lesson 08 of Level 1 measured this). A `rescue` that succeeds restores normal handler behaviour for that host.

## Retrying and waiting

`until` / `retries` / `delay` repeat a task (Level 1 · 07). For waiting on a TCP port, an HTTP status or a file, prefer `wait_for` and `uri` with `until`; they report timeouts clearly. For an operation that may take a long time, see async tasks (Level 3 · 05).

## Error handling on blocks: patterns

1. **Deploy with rollback.** `block`: apply; `rescue`: restore; `always`: remove temp files.
2. **Try an optional thing.** `block`: read an optional file; `rescue`: use a default (`ansible.builtin.set_fact`).
3. **Guard rails.** Use `assert` at the top of the play to fail fast before changing anything.
4. **Notify on failure only.** `rescue`: send a message, then `ansible.builtin.fail` to preserve the failure.
5. **Cleanup always.** `always`: remove locks, restore maintenance mode, close tickets.

## Check mode and blocks

In check mode, blocks and rescue behave the same way, but the commands inside may be skipped (Lesson 05 of Level 1), so a "failure" that depends on a real command's result may not occur; do not use check mode as a rescue-path test. To test rescue paths, write a test playbook that forces the failure (like the `/usr/bin/false` above) in a throwaway sandbox.

## Reading the recap

Counters: `ok`, `changed`, `unreachable`, `failed`, `skipped`, `rescued`, `ignored`. A run with `rescued=1` exited 0, which can mislead a pipeline into believing everything went well; if a rescue means "something went wrong", end it with `fail` or write an artifact (a summary line) that the pipeline checks. In the experiment the exit status was 0 even though the health check had failed and the rollback ran.

## How It Actually Works

A `block` is parsed into a `Block` object with three task lists. The strategy plugin executes the main list; when a task returns failure for a host, the executor marks the host as "in rescue" for that block, discards the rest of the block's main tasks for that host, and executes the rescue list with the failure details available as variables. After rescue (or without it), `always` runs. If rescue succeeded, the host's failed state is cleared for the enclosing scope and the recap increments `rescued`. Because state is tracked per host, one host can be in `rescue` while others complete the block normally, and under the `linear` strategy the rescue and always tasks are scheduled at their natural position, so hosts may wait at the next task boundary for each other.

## Common mistakes

- **Using `ignore_errors` to silence a problem** instead of deciding what failure means.
- **Rescue blocks that assume a particular failure point.**
- **A rescued run treated as success** by the pipeline.
- **Forgetting `always`** for cleanup of locks and temp files.
- **Failing in `rescue` with no log** of the original error.
- **Not using `any_errors_fatal`** for steps that must be all-or-nothing.
- **Relying on `failed_when` strings** that vary between tool versions.

## Exercise

1. Reproduce the block/rescue/always sequence and change the failing task to succeed; note which sections run.
2. Add `any_errors_fatal: true` to a two-host play where one host fails, and observe the difference.
3. Write a deploy block whose rescue restores a backed-up file and then fails the host so CI turns red.
4. Use `failed_when` to treat a command that returns 1 for "nothing to do" as success, and test both outcomes.
