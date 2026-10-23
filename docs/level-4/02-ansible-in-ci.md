---
description: "Ansible in CI/CD: a six-step pipeline script run for real, the non-idempotent task it caught, a linted workflow, and what CI cannot test."
---

# 02 · Ansible in CI/CD

Treat automation code like application code: every change is linted, tested on disposable targets and promoted through environments. This lesson builds a CI script for an Ansible repository, runs it, shows what it catches, and ties it to the CI/CD course on this site.

!!! note "What was run"
    `src/l4/ci.sh` is a six-step script, run with `ansible-core` 2.21.5 and `ansible-lint` against the Level 1 baseline playbook on two local "servers". The GitHub Actions workflow (`src/l4/workflow/ansible-ci.yml`) was written and checked with this site's sister course's workflow linter (`wflint.py`: 0 findings), but **was never run on GitHub**; its two action references use obviously fake SHAs that you must replace with real, reviewed ones. See the CI/CD Mastery Path course for the underlying CI/CD concepts.

## The pipeline, cheapest check first

```text
1 syntax-check      ansible-playbook --syntax-check
2 ansible-lint      production profile
3 secret hygiene    nologlint.py (tasks using secret variables need no_log)
4 converge          first run on a disposable target
5 idempotence       second run must report changed=0
6 check mode        --check must report changed=0 (no drift)
```

The ordering follows the CI/CD course's rule (Level 1 · 05): run the fastest, most likely to fail checks first. Steps 1 to 3 need no target and take seconds; steps 4 to 6 need a target and take longer.

### What each step caught

- **Step 2** failed on the Level 1 baseline playbook as I first wrote it: `Failed: 7 failure(s)` with `name[play]` (the play was unnamed) and six `name[casing]` findings (task names started with lowercase). The script stopped there, exactly as intended. I produced a lint-clean copy (`baseline_ci.yml`) by naming the play and capitalising the task names, after which the production profile passed.
- **Steps 4 to 6** on the clean copy: first run `changed=6` on both nodes, second run `changed=0`, check mode `changed=0`, and the script printed `CI OK`. About 3 seconds in total on a Mac with two local nodes.
- **Step 5 catches non-idempotent tasks.** I added a task that writes the current nanoseconds into a file (`lookup('pipe', 'date +%N')`). The pipeline got through steps 1 to 4 and then printed:

```text
== 5 idempotence (second run)
node1 : ok=6 changed=1
node2 : ok=6 changed=1
FAIL: second run reported 2 change(s)
```

and exited non-zero. A change that would flap on every run in production was stopped in review. The same defect passes steps 1 to 4 because nothing in them runs the playbook twice.

## Where Ansible runs in the pipeline

- **Test stage:** run against throwaway targets. Options: `connection: local` and a sandbox (as in this course), a container started per job, or a VM/cloud instance created for the job and destroyed afterwards. The cheaper the target, the faster the feedback; the more realistic, the more it proves.
- **Staging/pre-production:** run for real against an environment that mirrors production, ideally from the same Execution Environment image (Lesson 01).
- **Production:** run via a controller job or a protected pipeline environment with approval (CI/CD course, Level 2 · 07), with `--check --diff` output attached for the approver and a limit/batching strategy (Level 2 · 08, Level 3 · 07).
- **Scheduled:** a nightly drift audit in check mode (Lesson 06).

## The workflow file

```yaml
name: ansible-ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ansible-ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@<full commit SHA>
      - uses: actions/setup-python@<full commit SHA>
        with:
          python-version: "3.12"
      - run: |
          python -m pip install -r requirements.txt
          ansible-galaxy collection install -r requirements.yml -p ./collections
      - run: ./ci.sh playbooks/site.yml inventories/ci/hosts.ini
```

(The real file in `src/l4/workflow` has the same content.) The CI/CD workflow linter reported **0 findings**: least-privilege token, a job timeout, SHA-pinned actions (with obviously fake values here), and a concurrency group that cancels superseded runs (right for CI, wrong for a deploy job, CI/CD course Level 2 · 07).

Key decisions embedded:

- **Pinned tooling**: `requirements.txt` pins `ansible-core`, `ansible-lint` and Python libraries; `requirements.yml` pins collections. An unpinned install makes CI break when a new lint rule appears (a lint upgrade adds rules and fails old code).
- **Collections installed per project**, not globally.
- **Secrets**: the vault password comes from CI's secret store through an executable password script (Lesson 03), never from the repository.
- **Read-only token** for pull requests from forks; do not expose secrets to fork builds (CI/CD course, Level 4 · 01).

## Testing against containers: what it proves and does not

A container job (for instance a Debian or Rocky image) can verify package names, file templates, users and many config files across distributions quickly. It cannot verify behaviour that depends on a real init system, kernel settings (`sysctl`), firewalls, SELinux/AppArmor enforcement, or reboots. For those, use VMs, and consider testing a representative subset. Say clearly in your documentation what the CI tier covers. I did not run container jobs; the local-connection tests here have the same limitation, more strongly.

## Promotion and review

- **Pull request:** steps 1 to 6 on disposable targets; attach the lint and recap output.
- **Merge to main:** apply to staging automatically; run smoke tests.
- **Release to production:** a manual approval, with a `--check --diff` against production attached; then apply with batching.
- **Changes to roles** are versioned and released like libraries (Level 2 · 06; CI/CD course Level 3 · 07), with a changelog, so consumers pin versions.

## Make the pipeline testable and fast

- Keep each job under a few minutes; fast feedback matters (CI/CD course, Level 4 · 02).
- Cache the pip and collection downloads (CI/CD course, Level 2 · 02 for key design).
- Run roles' tests in parallel (a matrix over roles), and only the roles that changed (path filters, CI/CD course Level 2 · 09).
- Fail on warnings you care about: `ANSIBLE_DEPRECATION_WARNINGS`, lint `warn_list` aging (Lesson 09).
- Record artifacts: lint report, JUnit-style results (`ansible.builtin.junit` callback; needs the `junit_xml` Python library, not run), and the drift report from Lesson 06.

## How It Actually Works

The script is a sequence of commands whose exit statuses `set -e` propagates; the pipeline system treats a non-zero exit as a failed step. The idempotence assertion reads the `PLAY RECAP` lines (`host : ok=.. changed=..`), extracts each host's `changed` count with `sed`, sums them with `paste -sd+ | bc`, and fails if the sum is not zero. That parsing is only as reliable as the recap format; a more robust version uses a callback plugin that writes JSON (as Lesson 06 does) or the `junit` callback. The same facts that make the Level 1 tests work make this work: modules report `changed` truthfully, so a second run with zero changes is evidence of convergence.

## Common mistakes

- **Unpinned CI tooling.**
- **No second-run test**, so non-idempotent tasks reach production.
- **Running the real pipeline against production on every pull request.**
- **Secrets passed to fork builds.**
- **Believing a container test proves service behaviour.**
- **Parsing the recap with brittle shell** and never testing the parser.
- **One giant job** that takes 40 minutes and gets skipped.
- **Using `cancel-in-progress: true` on a production deploy group.**

## Exercise

1. Run `src/l4/ci.sh` on a playbook of yours (set `PATH` to include a virtualenv with `ansible-core` and `ansible-lint`). Record which step fails first and fix it.
2. Add a deliberately non-idempotent task and prove step 5 fails, then fix the task with `changed_when` or a module.
3. Replace the shell recap parser with the JSON drift report from Lesson 06 and write a test for it.
4. Adapt `ansible-ci.yml` to a matrix over three roles with path filters; run the CI/CD course's workflow linter on it.
