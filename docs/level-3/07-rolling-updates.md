---
description: "Rolling updates over eight simulated servers: drain, update, smoke test, rollback, and the always block that defeated max_fail_percentage."
---

# 07 · Rolling Updates and Failure Budgets

A rolling update changes a fleet in stages so that capacity stays up and a bad change is stopped early. Ansible's tools are `serial`, a failure budget, and per-batch checks. This lesson builds a rolling update over **eight simulated servers**, tests it, and reports a surprising result about how failure budgets interact with `block`/`always`.

!!! note "What was run"
    `src/l3/rolling/rollout.yml` runs against eight inventory hosts (`n1`..`n8`, local connection). Each "server" is a directory with a `version` file and an `in_rotation` marker file, and the "smoke test" is an `assert` that fails for hosts listed in a `bad_hosts` variable. **No real service, load balancer or health check was involved.** 11 pytest tests drive the real `ansible-playbook`; all passed after I changed the abort mechanism as described below.

## The playbook shape

```yaml
- name: Rolling update
  hosts: app
  serial: [1, "50%", "100%"]
  any_errors_fatal: true
  tasks:
    - name: Rollout block
      block:
        - Drain (remove from rotation)      # delete in_rotation marker
        - Log drain
        - Install new version               # write version file
        - Smoke test                        # assert host not in bad_hosts
      rescue:
        - Roll back to previous version
        - Log rollback
        - Fail the host so the batch is marked failed
      always:
        - Return to rotation                # recreate in_rotation marker
```

`serial: [1, "50%", "100%"]` on eight hosts gives batches of **1, 4 and 3**: the first is the canary, the second is 50% of the fleet (4), and the third is whatever is left (3). A test extracts the host counts per batch from the output and asserts `[1, 4, 3]`.

Principles in the structure:

1. **Drain first, re-enable last.** The host leaves rotation before its software changes and returns only after the smoke test. The `always:` section guarantees that a host is returned to rotation even when the update fails (it was rolled back to a working version), so a failure never leaves the fleet short of capacity because hosts were forgotten in a drained state. The test checks that after a failure **every host is back in rotation**.
2. **Roll back locally, then fail loudly.** The `rescue` restores the previous version on that host, logs it, and then deliberately **fails** the host. Without that final `fail`, a rescued host counts as recovered, the run would report success, and the next batch would proceed. Failing marks the batch failed.
3. **A canary first.** The batch of 1 reveals a bad build with minimal exposure.
4. **Verification is part of the batch.** The smoke test runs before the host is returned to rotation. Real ones: an HTTP health check with retries, a synthetic transaction, a check of error-rate metrics.

## Results from the tests

| Scenario | Outcome |
|---|---|
| All healthy | All eight at `2.0`, all in rotation, three batches ran, exit 0 |
| Canary (`n1`) fails smoke test | Exit non-zero; **all hosts at `1.0`** (the canary rolled back, nobody else touched); all in rotation; only one batch started; the canary's event log reads `drained`, `rolled back` |
| `n3` fails (second batch) | Exit non-zero; `n1` stays at `2.0` (first batch succeeded); `n3` back at `1.0`; `n6`, `n8` (third batch) still at `1.0`; all in rotation |
| Re-run after the fix | Finishes: all eight at `2.0` (hosts already updated are no-ops) |
| Run twice when healthy | Second run changes no versions |

The re-run case is why the playbook must be idempotent: the production workflow is "fix and run the same playbook again".

## A real finding: `max_fail_percentage` did not stop the rollout

My first version used `max_fail_percentage: 0`, expecting any failure to stop later batches. The test for "failure in the second batch" failed: the **third batch ran** (all of `n6`..`n8` were updated) even though `n3` had failed. To find out why, I wrote variants of a minimal play with `serial: [1, "50%", "100%"]` and `max_fail_percentage: 0`, failing only `n3`, and recorded which hosts started:

| Failure handling in the batch | Hosts that started |
|---|---|
| Plain task `fail` | `n1`..`n5` (third batch **stopped**, as expected) |
| `block` with `rescue: fail` (no `always`) | `n1`..`n5` (stopped) |
| `block` + `always:` (no rescue) | `n1`..`n8` (**did not stop**) |
| `block` + `rescue: fail` + `always:` | `n1`..`n8` (**did not stop**) |
| Any of the above with `any_errors_fatal: true` | `n1`..`n5` (stopped) |

So on **ansible-core 2.21.5**, a block with an `always:` section that ran after a failure let the play proceed to later batches despite `max_fail_percentage: 0` and a recap showing `failed=1`. I do not know whether this is intended or a bug, and I did not read the strategy source to find out; I measured it and pinned it in a test (`test_which_batches_start_after_a_failure_in_batch_two`, parametrised over four shapes). `any_errors_fatal: true` stops correctly in every shape, so the playbook uses that. If a future version changes the behaviour, the test fails and this section needs updating.

Lessons: (1) a **failure budget is a safety feature you must test**, not assume; (2) write a test that injects a failure in the middle batch and asserts later batches did **not** run; (3) the combination of `serial`, budgets and error-handling constructs is subtle, so prefer the simplest mechanism (`any_errors_fatal`) when the policy is "stop on any failure".

## Variations

- **Percent ramp.** `serial: [1, "5%", "25%", "100%"]` starts very small on large fleets.
- **Partial tolerance.** `max_fail_percentage: 20` allows a few failures within a batch (useful when machines are individually flaky), with the caveats above. Check what it does with your error-handling shape.
- **Wait between batches.** `ansible.builtin.pause` (interactive) or `wait_for` on a metric check, to let monitoring see the new version before proceeding. Automate the decision with a health query where possible; a canary analysis loop is covered in the CI/CD course (Level 3 · 01).
- **Zero-capacity risk.** If capacity per host is high, draining 50% at once may overload the rest. Compute the headroom (CI/CD course, Level 3 · 01) and choose batch sizes so the fleet can serve peak load with the hosts removed.
- **Database migrations** are not rolling; run them once (`run_once`) before the app rollout with expand/contract (CI/CD course, Level 3 · 03).

## Operating the playbook

1. Start with `--check --diff --limit canary-host`.
2. Run on the canary alone, watch metrics.
3. Run the full playbook; keep a human watching the first batch and the 50% batch.
4. On failure: do not just re-run. Read the failure, decide fix vs revert. A re-run after a fix is safe by design; a re-run of a broken change just fails again and burns a canary.
5. Record what was deployed (version, hosts, time, who) as evidence (CI/CD course, Level 4 · 05).

## How It Actually Works

`serial` splits the host list of a play into batches and executes the full task list for each batch in sequence, as separate runs of the play (the output shows a new `PLAY` header per batch). Between batches the executor evaluates whether the run should continue: it counts hosts that failed in the batch and compares the percentage with `max_fail_percentage`, and `any_errors_fatal` makes any host failure abort the play for all hosts immediately. The observed discrepancy suggests that hosts which ran an `always:` section after a failure are bookkept differently from hosts that stopped at the failure, so the batch's failed count did not exceed the limit; I have not confirmed the cause. Blocks, rescue and always are implemented by the same iterator that tracks per-host state, so a host in the "always" phase is still running tasks.

## Common mistakes

- **No failure test** for the abort path.
- **Trusting `max_fail_percentage`** with complex error handling constructs.
- **A rescue that doesn't fail**, so the run proceeds as if healthy.
- **Forgetting to return hosts to rotation** after a failed update.
- **A single large batch** for a risky change.
- **Smoke tests that always pass** (not checking the thing that changed).
- **Rolling out a change that is not backward compatible**, since old and new versions run together.

## Exercise

1. Run `pytest src/l3/rolling` and read the parametrised test. Change `serial` to `[2, "100%"]` and predict, then verify, the batch sizes.
2. Add a `post_tasks` metric check that fails the batch if a (simulated) error rate file exceeds a threshold.
3. Make the rollback itself fail on one host and decide what the playbook should do (alert, leave it drained, stop the world). Implement and test it.
4. Add a `--tags drain-only` mode that only drains the hosts, for maintenance, and ensure `always` does not return them to rotation in that mode.
