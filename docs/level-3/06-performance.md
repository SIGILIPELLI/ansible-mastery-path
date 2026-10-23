---
description: "Ansible performance measured on 20 local hosts: forks scaling from 50 s to 4.5 s, fact gathering costs, gather_subset, fact caching, and what else to tune."
---

# 06 · Performance: Forks, Pipelining and Facts

Ansible's speed is rarely a problem for ten servers and often a problem for a thousand. Most of the time goes to three things: waiting on tasks (parallelism), gathering facts, and connection overhead. This lesson measures the first two and describes the third.

!!! note "What was run, and how to read the numbers"
    I timed real `ansible-playbook` runs (ansible-core 2.21.5) against **20 inventory hosts that all use `ansible_connection=local`** on one 8-core Mac, each task being `sleep 1` or a fact gather. Each configuration was run **once**, so treat the figures as indicative, not as benchmarks; repeat several times for decisions. With the local connection there is **no SSH**, so connection setup, pipelining, ControlPersist and network latency (the other big costs in real fleets) are not captured. Those are described from the documentation and not measured.

## Forks: how many hosts run in parallel

`forks` (default 5) is the number of worker processes handling hosts at once. The playbook: 20 hosts × 2 tasks of `sleep 1`, facts off.

| `-f` | Wall time |
|---|---|
| 1 | 50.1 s |
| 5 | 11.1 s |
| 10 | 6.6 s |
| 20 | 4.5 s |

The ideal times are 40 s (1 fork: 20 hosts × 2 s), 8 s (5), 4 s (10) and 2 s (20); the measured values are higher by a roughly constant per-run and per-host overhead (about 0.5 s of process start-up plus per-task bookkeeping). Notes:

- Scaling is close to linear until forks reaches the host count, and then stops: 20 forks cannot help 20 hosts beyond one round.
- `-f 20` isn't free: each fork is a separate Python process holding inventory data. On a small controller, hundreds of forks use a lot of memory and CPU; on a real SSH fleet, the controller's CPU and the network become the limit. Increase gradually and watch.
- The default of 5 is conservative and is often the cheapest single tuning (`forks = 20` or more in `ansible.cfg`).
- Under the `linear` strategy a slow host holds up the others at each task (Level 2 · 08); `free` helps when host speeds differ.

## Facts: the hidden fixed cost

`gather_facts` runs the `setup` module on every host at the start of each play. Same 20 hosts, `-f 20`:

| Configuration | Wall time |
|---|---|
| facts off (`gather_facts: false`), one `debug` task | 0.4 s |
| `gather_facts: true`, `gather_subset: all` (default) | 2.3 s |
| `gather_subset: min` | 2.1 s |
| `gather_facts: smart` + JSON fact cache, **first** run (fills cache) | 2.3 s |
| same, **second** run (cache hit) | 0.4 s |

Reading it: gathering all facts added about **1.9 seconds** to a play that does nothing else, so a playbook with ten plays that each gather facts spends 19 s on facts alone, even on a local machine. Real hosts over SSH take longer. Three ways to cut it:

1. **Turn it off** where you do not use facts (`gather_facts: false`). Many plays only copy files.
2. **Limit it** with `gather_subset` (for example `min`, or `!all,!min,network`). On this Mac, `min` saved only 0.2 s (2.1 vs 2.3), so the dominant cost was the process and the base facts; the saving is larger on hosts where hardware or network discovery is slow. Measure on yours.
3. **Cache it**: with `gathering = smart` and a cache plugin (`jsonfile`, `redis`, ...), facts gathered on one run are reused, and the second run skipped gathering (0.4 s). The cache for 20 hosts was 20 JSON files totalling 400 KB. Caches go **stale**: the value of `ansible_facts.memtotal_mb` may be days old; set a timeout (I used 600 s) and gather fresh facts when you need current values (for example `setup` explicitly, or `gather_facts: true` in the plays where it matters). A stale cache can also hold facts about a host's previous OS after a rebuild.

Fact caching also lets a play read other hosts' facts through `hostvars` without gathering them in this run.

## Connection costs (described, not measured)

Over SSH every task does: copy the module (one or more SFTP/`scp` operations), execute it, and clean up. Settings from the Ansible documentation that reduce the round trips:

- **SSH pipelining** (`pipelining = True`): sends the module through the existing SSH session's stdin instead of writing a temporary file first, cutting round trips substantially. It needs `requiretty` to be disabled in `sudoers` on the target when using `become`.
- **ControlPersist / ControlMaster**: reuse one SSH connection for many tasks (Ansible enables this by default through `ssh_args`).
- **`strategy = free`**, **`async`** for long tasks, and **`mitogen`** (a third-party strategy plugin, not maintained for current versions as far as I know; check) are other options.
- **Lower-latency placement**: run Ansible from a host close to the fleet (a controller in the same network, not a laptop on a VPN).

If you tune only one SSH setting, pipelining is usually the biggest; verify with timing on your own infrastructure.

## Reduce the work, not just the time

The cheapest speed-up is to run fewer tasks on fewer hosts:

- **Limit** and **tags** (Level 2 · 07): apply one role to one group.
- **Avoid redundant tasks**: replace a loop that calls a module 50 times with a module call that takes a list (one `package` call with a list rather than a loop).
- **Use `when` guards that avoid an expensive module** instead of letting it figure out nothing is needed.
- **Template once**, not per host, when the output is identical (`run_once` with `delegate_to`).
- **Short-circuit with `stat`** only if the stat is cheaper than the work.
- **Split playbooks** by lifecycle: provisioning once, configuration often, deployment constantly.

## Measuring properly

1. Use `ansible-playbook` with the `profile_tasks` callback (`ANSIBLE_CALLBACKS_ENABLED=ansible.posix.profile_tasks`, from the `ansible.posix` collection; not run here) to see time per task, or `timer` for a total.
2. Repeat runs and report the median.
3. Change one variable at a time.
4. Keep the target conditions identical (cold vs warm caches, load).
5. Measure on the real connection type before choosing a setting.

My timing harness was a small shell function recording `date` before and after a run, with output discarded, which includes Python and Ansible start-up (a run with facts off and one trivial task took 0.4 s). That is adequate for 2× effects, and not for 5% ones.

## How It Actually Works

The controller's task queue manager starts a fixed pool of worker processes (`forks`). For each task, the strategy plugin hands each host's work item to an idle worker; a worker templates the arguments, opens or reuses the connection, ships the module, and reports the result back to the main process over a queue. With `forks` smaller than the number of hosts the strategy runs hosts in waves, so total time ≈ ceil(hosts / forks) × per-host task time, which matches the table (20 hosts at 5 forks is four waves of 2 s plus overhead, so roughly 8 s + 3 s). Fact gathering is just another task (the `setup` module) executed for every host before the first task; its output is stored in memory per host, and the cache plugin interface lets that storage persist between runs. The 1.9 s difference between 0.4 s and 2.3 s is the fact module's work (starting it on 20 hosts and enumerating hardware, network, mounts and environment); I did not profile it further.

## Common mistakes

- **Leaving forks at 5** for large fleets.
- **Gathering facts in every play** when they are never used.
- **Caching facts without expiry** and acting on stale data.
- **Optimising before measuring**, or measuring once.
- **Raising forks beyond what the controller can handle.**
- **Loops of single-item module calls** where a list-taking module exists.
- **Running Ansible over a high-latency link** and blaming Ansible.

## Exercise

1. Reproduce the forks table with your own inventory of local hosts, three runs each, and report medians.
2. Measure `gather_subset: min` versus `all` on a real remote host if you have one.
3. Enable the JSON fact cache with a short timeout and demonstrate stale data: change a custom local fact and show the old value is served until expiry.
4. Pick a slow playbook of your own, list its five slowest tasks (use `profile_tasks`), and propose one change for each.
