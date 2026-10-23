---
description: "Level 2 project: a webapp role with validation and handlers, a 9-test suite using real ansible-playbook and ansible-lint, and a role-param finding."
---

# 10 · Project — A Tested Role

This project turns the Level 2 ideas into a small, finished artefact: a role with a documented interface, validation, a handler, and a test suite that proves it behaves. The tests run the real `ansible-playbook` against local hosts and the real `ansible-lint`.

!!! note "What was run, and what wasn't"
    The role is `src/l2/roles/webapp`; the tests are `src/l2/test_role.py` (**9 tests, all passed**, 16 seconds) and run on a Mac with ansible-core 2.21.5 and `ansible-lint` in the same virtual environment. They run two inventory hosts with `ansible_connection=local`; the role manages a config file and directory, so nothing about packages, services or privilege escalation is tested. The suite was written after the role and one assumption in it was wrong (below), which is reported rather than hidden.

## The role

- **Interface** (`defaults/main.yml`): `webapp_port` (8080), `webapp_workers` (2), `webapp_root` (a per-host directory under a sandbox, derived from `inventory_hostname` so two hosts never share a file).
- **Internal constant** (`vars/main.yml`): `webapp_config_mode: "0644"`.
- **Tasks**: validate (`assert` on port range 1..65535 and workers >= 1, `quiet: true`), create the directory (`0755`), render `webapp.conf` from a template (mode from the constant) and `notify: Reload webapp`.
- **Handler**: `Reload webapp` (a `debug` message standing in for a service reload).
- **Docs**: a README with a table of variables, defaults and meanings. `meta/main.yml` has real metadata (author, license, a string `min_ansible_version`, platform list).

## The tests

| Test | Asserts |
|---|---|
| defaults and per-host override | `w1` file has `port=8080`; `w2`, with host var `webapp_port=9000`, has `port=9000` |
| role parameter overrides default | `vars: {webapp_workers: 7}` produces `workers=7` |
| idempotent | second run: exit 0 and `changed=0` for every host |
| handler fires only on change | first run: exactly one `RUNNING HANDLER`; second run: none |
| invalid port fails before changing anything | `webapp_port=70000`: non-zero exit, the message `webapp_port must be ...` appears, and the output directory does not exist |
| zero workers rejected | `webapp_workers=0`: non-zero exit |
| check mode writes nothing | `--check`: exit 0, output directory not created |
| role parameter beats `vars/main.yml` | passing `webapp_config_mode: "0600"` yields a file with mode `0600` |
| lint | `ansible-lint roles/webapp` exits 0 (production profile) |

The harness writes an inventory in a temporary directory so each test is isolated, points `ANSIBLE_ROLES_PATH` at the role, sets `ANSIBLE_HOME` inside the project to keep temp files out of the real home directory, parses the `PLAY RECAP`, and skips itself if Ansible is not installed.

### The wrong assumption

I first intended a test showing that `vars/main.yml` "protects" an internal constant from callers: pass `webapp_config_mode: "0600"` as a role parameter and expect `0644`. I was not sure what would happen, so I wrote the assertion loosely (either value accepted) to see, then measured: the file ended up `0600`. **Role parameters outrank the role's own `vars/main.yml`**, consistent with Ansible's documented precedence order, and consistent with the Lesson 02 experiment, which did not include role parameters (it covered `vars/main.yml` as source 5). The test now asserts the measured outcome and its comment says why. Takeaway: `vars/main.yml` is for constants that should not be overridden *by accident* (an inventory variable loses to it), not a security boundary against callers who pass role parameters or `-e`.

### Another finding: lint on the scaffold

`ansible-galaxy role init` produces a role that **fails** `ansible-lint`: sample metadata and a numeric `min_ansible_version: 2.2` that YAML reads as a float (`schema[meta]: ... 2.2 is not of type 'string'`). After editing `meta/main.yml`, removing the sample `tests/` scaffold, and rewriting the tasks with FQCNs, names and quoted modes, the role passed the **production** profile.

## How to extend this role realistically

For a role that manages a real service, add (each is a Level 2/3 topic):

1. A `package` task and a `service` task, with `ansible_facts.os_family` branching via `include_vars` for package names; test in containers for the files, in a VM for the service.
2. `validate:` on the template to check the config before replacing the live file.
3. A `meta/argument_specs.yml` describing the role's variables (types, required, choices): Ansible validates role arguments against it before running tasks, which replaces much of the hand-written `assert` and documents the interface in machine-readable form.
4. Handlers that restart only when configuration changed, plus `meta: flush_handlers` before a health check.
5. A `verify.yml` playbook that checks the end state and can run read-only against production.
6. A changelog and version tags if you publish it to a collection (Lesson 06).

## Reading the results

When all tests pass, you have evidence for these claims: the interface works as documented; invalid input is rejected before any change; repeated runs converge; handlers fire once per real change; check mode is safe; and the role meets the community lint profile. You do **not** have evidence that the managed service works, that permissions are right for a real service account, or that the role survives an upgrade of ansible-core. Those need a real target and a version matrix.

## Checklist

- The role's interface is `defaults/main.yml` and a README table, nothing else.
- Inputs are validated before any change, and a test proves it.
- Every host-specific path includes `inventory_hostname`.
- The second run reports `changed=0`, and a test asserts it.
- The handler fires only on a real change, and a test counts it.
- Check mode writes nothing, and a test proves it.
- `ansible-lint` passes the production profile in CI with a pinned version.
- The role's tests run in under a minute so people run them.
- Behaviour you were unsure of (precedence, defaults) is measured and pinned by a test.

## Running a subset

```bash
python3 -m pytest -q src/l2/test_role.py                      # the role suite (about 16 s)
python3 -m pytest -q src/l2/test_role.py -k "idempotent or handler"
python3 -m pytest -q src/l2/prec                              # the precedence experiment (a few runs of Ansible)
```

The tests skip themselves with a clear reason if `ansible-playbook` or `ansible-lint` is missing, so a plain `pytest` on a machine without them does not fail spuriously.

## How It Actually Works

The tests are an outer loop around Ansible: each one builds a tiny project in a temp directory (an inventory file and a playbook that applies the role), invokes `ansible-playbook` as a subprocess, and inspects two things: the process's exit status and output, and the resulting files. Ansible's own contract provides the signals: `changed` counts in the recap (for idempotency), the `RUNNING HANDLER` marker (for handler behaviour), the exit status (for failure), and the filesystem (for effects). Because role loading is by name along `ANSIBLE_ROLES_PATH`, the test needs no copying of the role into each temp project, and because each project uses its own temporary sandbox directory, tests are independent and can run in any order.

## Common mistakes

- **Writing tests that only check the happy path.**
- **Asserting what you hope is true** about precedence instead of measuring it.
- **Sharing a sandbox** across tests, causing order dependence.
- **Not running lint on generated scaffolds.**
- **Treating `vars/main.yml` as unoverridable.**
- **Skipping the second-run test.**
- **Tests that are so slow nobody runs them**; keep a fast subset.

## Exercise

1. Run `python3 -m pytest -q src/l2/test_role.py` (with `ansible-core` and `ansible-lint` installed) and read each test.
2. Add `meta/argument_specs.yml` for the role and remove the `assert` task; write a test that an invalid type is rejected.
3. Add a `webapp_enabled` boolean that controls whether the config is rendered, with tests for both values and for a string `"false"` passed with `-e`.
4. Add a second role `webapp_logrotate` and a playbook that applies both; test that applying both is idempotent and that each role's handler fires independently.
