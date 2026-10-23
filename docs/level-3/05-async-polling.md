---
description: "Async tasks and polling: async, poll and async_status, fire-and-forget, retries until finished, and the confusing message produced when a job times out."
---

# 05 · Async Tasks and Polling

Normally Ansible keeps a connection open for the whole life of a task. A task that takes ten minutes (a large download, a database restore, a long build) risks a dropped SSH connection or a timeout, and blocks everything else behind it. **Async** runs the task in the background on the target and lets the controller check on it.

!!! note "What was run"
    `src/l3/asy.yml` run on macOS with a local connection and `sleep` as the "long job". With `connection: local` there is no network to drop, so the *reasons* to use async (flaky or long connections) were not reproduced; the mechanics and messages are real for ansible-core 2.21.5.

## The three modes

```yaml
- name: fire and forget style (poll 0)
  ansible.builtin.command: sleep 3
  async: 10          # allow up to 10 seconds
  poll: 0            # do not wait; return a job id immediately
  register: job
```

1. **`async: N, poll: M`** (M > 0): start the task, then check every M seconds until it finishes or N seconds pass. The task still blocks the play, but the connection is not held open the whole time (Ansible polls). Use this for long tasks on unreliable connections.
2. **`async: N, poll: 0`**: start it and **move on**. The task result contains `ansible_job_id`; you check later with `async_status`. Use this to start work on many hosts in parallel and to do other work meanwhile.
3. No `async`: ordinary blocking behaviour.

## Starting and checking

My run started a 3-second job with `poll: 0` and printed `started job j443061854556.15009 finished=False`. Then a normal task ran (`echo working`) while the job continued. Then:

```yaml
- ansible.builtin.async_status: {jid: "{{ job.ansible_job_id }}"}
  register: res
  until: res.finished
  retries: 6
  delay: 1
```

Output: three `FAILED - RETRYING ... (5, 4, 3 retries left)` lines (these are expected, the job was not done yet), then `finished=True rc=0 attempts=4`. The retries are `until` retries, not failures. Set `retries * delay` comfortably above the job's expected duration.

Details:

- The `async_status` task polls the **status file** the job writes on the target (under `~/.ansible_async/<jid>`); the job id identifies it.
- You can start jobs on all hosts with `poll: 0`, then collect them with a loop of `async_status` over the registered results: a simple way to do parallel work within a single play beyond `forks`.
- Use `ansible.builtin.async_status` with `mode: cleanup` to remove status files when many jobs run, so they do not accumulate.
- The task's own `changed`/`failed` outcomes appear in the final status; with `poll: 0` the *start* task is reported ok even if the job later fails, so you must check the final status.
- Handlers, `notify` and `register` on the start task refer to the start, not the finish.

## When the job exceeds `async`

```yaml
- ansible.builtin.command: sleep 5
  async: 1
  poll: 1
  ignore_errors: true
```

The result on this version was an error that is not very informative:

```text
ASYNC FAILED on localhost: jid=j779617292782.15095
fatal: [localhost]: FAILED! => {"async_result": {"ansible_job_id": "...", "finished": false, "started": true, "results_file": "~/.ansible_async/...", ...}, "msg": "async task produced unparsable results"}
```

So an exceeded time limit appears as `async task produced unparsable results`, with `finished: false` inside `async_result` as the real clue (I did not investigate why this version words it so; other versions may say something different). Treat `finished: false` plus that message as "the job outlived `async`". The background process may be killed or may continue; check the target. The lesson: **set `async` higher than the longest legitimate run**, and alert on this error.

## When to use async

Good uses:

- A long task (more than the connection's idle timeout, or more than a few minutes) such as a backup, a big package upgrade or an image pull.
- Starting a slow operation on every host at once and doing other tasks while it runs.
- Operations that restart the SSH daemon or the network (the connection will drop; start with `poll: 0`, wait with `wait_for_connection`).

Poor uses:

- Short tasks. Async adds overhead and complexity.
- As a general way to speed up playbooks; raising `forks` or reducing fact gathering is simpler (Lesson 06).
- Tasks whose result you need immediately to continue.

## Related tools

- `wait_for` waits for a port, a file, or a string in a file, with a timeout; `wait_for_connection` waits until the host can be managed again (after a reboot).
- `ansible.builtin.reboot` reboots and waits for the host to return (not run here).
- `throttle` limits concurrency of a specific task.
- For work lasting hours, a job scheduler or a pipeline is better than a playbook. Playbook runs should be bounded.

## Pitfalls

- **Async plus check mode**: async tasks do not run in check mode like others; treat their check-mode results as unreliable.
- **Async plus `become` and files**: the status file lives in the *user's* home directory on the target; with a different `become_user` use `async_dir` consistently.
- **Variable lifetime**: `job.ansible_job_id` is only available from the `register`; if the playbook fails between start and check, the job keeps running orphaned. Put start and status in the same block with `always:` cleanup.
- **Idempotency**: the command in the job must itself be safe to repeat. A failed run that starts the job again may start a second copy while the first still runs.

## How It Actually Works

With `async`, the controller wraps the module in an **async wrapper** (`async_wrapper`) shipped to the target. The wrapper forks into the background, runs the real module, and writes its JSON result to a file named after a generated job id in the async directory (default `~/.ansible_async/`). It returns immediately with the job id. Polling is just repeated execution of a tiny module (`async_status`) that reads the file: if it is missing or incomplete the job is still running (`finished: 0`); if complete it returns the saved result. With `poll: N > 0` the controller does that polling loop itself, sleeping N seconds between checks. A job that runs past `async` seconds is terminated by the wrapper's timeout logic, leaving an incomplete result file, which explains why the controller reports it as unparsable rather than as a timeout.

## Common mistakes

- **`async` shorter than the job.**
- **Starting with `poll: 0` and never checking**, so failures go unnoticed.
- **`retries` too small** for `async_status`.
- **No cleanup** of status files and orphaned jobs.
- **Using async to hide a slow design.**
- **Assuming the start task's `ok` means the job succeeded.**
- **Ignoring the `finished: false` clue in the error.**

## Exercise

1. Reproduce the three runs (poll 0 plus `async_status`; `poll: 1`; timeout) and list the exact messages for your version.
2. Start the same 2-second job on 10 hosts with `poll: 0`, then collect them with a loop. Compare the total time with a normal run.
3. Wrap start and status in a block with `always:` that cleans up status files, and force a failure between them.
4. Write a task that restarts a service which drops the connection, using `poll: 0` and `wait_for_connection`.
