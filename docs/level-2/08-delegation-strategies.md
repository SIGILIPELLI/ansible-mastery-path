---
description: "Delegation, run_once, serial batches, max_fail_percentage and the free strategy, measured on four local hosts, including a delegated-vars error."
---

# 08 · Delegation, Serial Batches and Strategies

Some tasks must run on a different machine from the one being configured (take a host out of a load balancer, register it in a monitoring system). Some must happen only once for the whole group. Some must proceed in small batches so a mistake does not take everything down. Ansible provides `delegate_to`, `run_once`, `serial`, and execution strategies for these.

!!! note "What was run"
    Four local hosts `n1`..`n4` (`ansible_connection=local`) and the playbooks `serial.yml`, `deleg.yml` and `strat.yml` in `src/l2`, run with ansible-core 2.21.5. Real load balancers, rolling restarts of services and SSH delegation were not exercised.

## `delegate_to`

`delegate_to: host` runs the task on another host while keeping the *variable context* of the original one. A typical use:

```yaml
- name: remove this host from the load balancer
  ansible.builtin.uri: {url: "http://lb.example/api/drain/{{ inventory_hostname }}", method: POST}
  delegate_to: lb1
```

Each web host triggers one call from `lb1`'s side (or `localhost` to call an API from the controller), and `{{ inventory_hostname }}` is still the web host. The task's own connection settings come from the delegated host. In my test, a delegated `command` ran on `n4` for each of four hosts; the output was the right messages with all four hosts' names.

Gotchas:

- **`ansible_delegated_vars`** exists only inside the delegated task's context. I referenced `ansible_delegated_vars['n4']` from a *later, ordinary* `debug` task and got `'ansible_delegated_vars' is undefined`. To use delegated host data later, register the result or use `hostvars['n4']`.
- **Facts gathered during a delegated task** are assigned to the delegated host only with `delegate_facts: true`; otherwise they attach to the original host.
- **`command` is not a shell.** My delegated command used `$(basename $PWD)` and printed it literally (`registering n1 from $(basename /Users/.../l2)`): the `command` module does not run a shell, so `$()` is not evaluated. Use `shell` when you need substitution (and then own the idempotency and quoting).
- **Parallel delegated tasks** against one host can race: all four hosts ran the delegated task on `n4` at once. If the delegated action is not safe to run concurrently (editing one file), use `serial: 1` or a `throttle`.

## `run_once`

```yaml
- ansible.builtin.debug: {msg: "run_once ran for {{ inventory_hostname }}"}
  run_once: true
```

Printed `run_once ran for n1`: the task ran on the **first host of the play batch** only. Its result is copied to the other hosts' variable context, so a `set_fact` with `run_once` is visible everywhere: my `token` variable showed the same value (`tok12839`) on `n1`..`n4`. Typical uses: database migrations (once per cluster), sending one notification, creating one shared resource. Warnings:

- With `serial`, `run_once` runs once **per batch**, not once overall. Combine carefully (`when: inventory_hostname == ansible_play_hosts_all[0]` is the explicit alternative).
- It runs on the first host, so if you `--limit` the run, the first *limited* host does the work.
- If the first host fails the task, the whole group is treated as failed for that task.

## `serial`: rolling batches

`serial: 2` on four hosts ran the entire play in two passes: first `n1`+`n2` for all tasks (A and B), then `n3`+`n4`:

```text
PLAY [app]  A on n1  A on n2  B on n1  B on n2
PLAY [app]  A on n3  A on n4  B on n3  B on n4
```

`serial` also accepts a percentage (`"25%"`) or a list for a ramp (`[1, 3, "100%"]`): one host as a canary, then three, then everyone. Batches are the basic mechanism of a rolling update (Level 3 · 07).

### Failure budgets

`max_fail_percentage` stops the play if too large a share of a **batch** fails. Measured on four hosts with a task that fails on chosen hosts:

| Setting | Failing hosts | Result |
|---|---|---|
| `serial: 1`, default (0%) | `n1` | `n1` failed; **`n2`..`n4` never ran** (the play aborted) |
| `serial: 2`, `max_fail_percentage: 50` | `n1` (1 of 2 = 50%) | batch continued; `n2` finished; **`n3` and `n4` ran** |
| `serial: 2`, `max_fail_percentage: 50` | `n1` and `n2` (100% > 50%) | play aborted; **`n3` and `n4` never ran** |

Two details to remember: the threshold is "strictly more than" (50% failures of a batch of two does not abort at 50), and with the default of 0 any failure in a batch stops later batches. With `serial: 1` and a default budget, one bad host protects the rest of the fleet, which is the point: a broken change is stopped after one machine. `any_errors_fatal: true` is the stricter setting (stop everything on the first failure, even within a batch).

## Strategies

The `strategy:` keyword selects how tasks are scheduled across hosts:

- **`linear`** (default): every host finishes task N before any host starts N+1.
- **`free`**: each host runs through the tasks as fast as it can.
- **`host_pinned`** and **`debug`** exist for special cases (not run).

Measured: host `n1` sleeps 2 seconds on task 1, the others 0; the second task prints the seconds of the clock.

```text
linear: second task on n1, n2, n3, n4 all at :45   total ~2.96 s
free:   n4, n2, n3 at :46; n1 at :48               total ~2.99 s
```

Under `linear` the fast hosts waited for `n1` and all printed the same second. Under `free` they ran ahead by two seconds. Total time was the same here (the slow host dominates in both), but `free` helps when tasks take very different times per host and later tasks do not depend on other hosts. Output ordering under `free` is non-deterministic, and tasks that expect other hosts to be at the same point (a "wait until everyone is done" step) break.

## `throttle` and `forks`

`throttle: 1` on a task limits it to one host at a time without changing the rest of the play (useful for a step that hits a rate-limited API). `forks` (`-f`, default 5) caps how many hosts run a task concurrently across the whole run. A play on 100 hosts with `forks=5` takes at least 20 rounds per task (Level 3 · 06 measures fork effects).

## Orchestrating a rolling change

A common structure for a service update:

```yaml
- hosts: web
  serial: [1, "25%", "100%"]
  max_fail_percentage: 0
  tasks:
    - ansible.builtin.include_tasks: drain.yml        # delegate_to: lb
    - ansible.builtin.include_role: {name: webapp}
    - ansible.builtin.include_tasks: smoke_test.yml   # fail the batch if unhealthy
    - ansible.builtin.include_tasks: undrain.yml
```

One canary host, a quarter of the fleet, then everyone; any failure stops the rollout. This is the CI/CD course's rolling and canary ideas (Level 3 · 01) applied with Ansible primitives.

## How It Actually Works

`serial` makes the play executor split the matching host list into batches and run the whole task list for each batch in turn, re-evaluating the play for each (including `run_once` and handlers per batch). `delegate_to` changes only the connection: the task's templated arguments use the original host's variables, but the executor opens (or reuses) a connection to the delegated target. `run_once` selects the first host in the current batch and runs the task there, then copies the result to the others through `register`/`set_fact` machinery. The `linear` strategy is a loop that sends task N to all hosts' workers and waits for all results before proceeding; `free` gives each host's worker its own iterator over the task list. `max_fail_percentage` is evaluated after each batch finishes a task, against the number of hosts in the batch.

## Common mistakes

- **`run_once` with `serial`** and expecting one run in total.
- **Delegated tasks racing** on a shared target.
- **Using `ansible_delegated_vars` outside the delegated task.**
- **Assuming `command` evaluates shell syntax.**
- **No failure budget on a rolling change**, so a bad change reaches the whole fleet.
- **`free` strategy with cross-host dependencies.**
- **Draining and undraining in separate plays** so a failure leaves a host out of rotation; wrap in `block` with `always`.

## Exercise

1. Reproduce the `serial` and `max_fail_percentage` table on four local hosts and add a case with `serial: [1, 3]`.
2. Write a play that gets a token with `run_once` and `delegate_to: localhost`, stores it with `set_fact`, and uses it on every host. Run it with `--limit` for two hosts and note who performs the `run_once`.
3. Make a task slow on one host and compare the wall-clock time of `linear` and `free` with 8 hosts and `forks=3`.
4. Add a drain/undrain pair to a rolling play so the host is always put back, even when the middle task fails.
