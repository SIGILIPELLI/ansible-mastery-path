---
description: "Testing and linting Ansible: ansible-lint findings measured, syntax checks, running twice, check-mode tests, and where Molecule and containers fit."
---

# 09 · Testing and Linting Ansible

Infrastructure code deserves tests as much as application code. Fortunately Ansible has a testing ladder, from instant static checks to full runs in disposable environments. This lesson works up the ladder with real runs and says where each rung stops being informative.

!!! note "What was run"
    `ansible-lint` and `ansible-playbook` (syntax checks, repeated runs, check mode) were run for real, ansible-core 2.21.5 and ansible-lint from the same venv. **Molecule** (the usual role testing framework) and container-based testing were **not** run (no container runtime). Findings are copied from an actual lint run on a deliberately bad playbook.

## Rung 1: syntax check

`ansible-playbook --syntax-check site.yml` parses the playbook without connecting. It catches YAML and structural errors (Level 1 · 04), not undefined variables or wrong arguments. It is instant; run it everywhere, including editor hooks.

## Rung 2: ansible-lint

`ansible-lint` applies a catalogue of rules. On this playbook:

```yaml
- hosts: all
  tasks:
    - shell: echo hello > /tmp/x
    - name: copy file
      copy: src=a dest=/tmp/a mode=0644
    - command: mkdir /tmp/foo
    - name: Ensure latest
      package: name=foo state=latest
```

it reported **13 violations** and failed, summarised as:

| Rule | Count | Meaning |
|---|---|---|
| `fqcn` | 4 | Use `ansible.builtin.shell`, not `shell` |
| `name` (missing/casing/play) | 4 | Name plays and tasks, start names uppercase |
| `no-changed-when` | 2 | `command`/`shell` without `changed_when` (breaks idempotency reporting, Level 1 · 05) |
| `no-free-form` | 2 | Avoid `copy: src=a dest=b` free-form arguments |
| `package-latest` | 1 | `state: latest` makes runs non-reproducible |

Each message gives the rule, the file and line, and a suggested fix. The corrected playbook:

```yaml
---
- name: Example
  hosts: all
  gather_facts: false
  tasks:
    - name: Create directory
      ansible.builtin.file:
        path: /tmp/foo
        state: directory
        mode: "0755"
```

passed with `Last profile that met the validation criteria was 'production'`. ansible-lint has **profiles** (`min`, `basic`, `moderate`, `safety`, `shared`, `production`) in increasing strictness; the output tells you the highest your content satisfies. Start by getting to `basic`, then raise the bar.

Linting my own role was instructive: the first run of `ansible-lint roles/webapp` failed on `meta/main.yml` because `galaxy_info.min_ansible_version` was the number `2.2` instead of a string (YAML parsed `2.2` as a float), plus sample metadata left by `galaxy init` and two YAML formatting issues. After fixing them the production profile passed. The scaffold created by `ansible-galaxy role init` does not pass lint without editing.

Lint cannot know whether your logic is right. It is fast, deterministic and finds a lot, so run it on every pull request, with a project config (`.ansible-lint`) that documents any disabled rules and the reason. It needs to be pinned like any dependency, because a new version adds rules that suddenly fail old code.

## Rung 3: idempotence and check mode on a real run

The cheapest dynamic test: apply twice and assert `changed=0` on the second run. Add a check-mode run after the apply and assert `changed=0` too. The Level 1 baseline project does this with `pytest` calling the real `ansible-playbook` (8 tests, 53 s), and the Level 2 role project does it (below). It requires a target to apply to:

- **localhost with `connection: local`** and a sandbox directory (as in this course) is good for file, template and variable logic.
- **Containers** are good for package and file logic across distributions; start from the distribution image, run the playbook, run it again, and run assertions. Not for `systemd`, kernel parameters or anything needing a real init system.
- **Virtual machines** (Vagrant, cloud instances created in CI) are slower but test the real thing, including services and reboots.

Molecule automates this: it creates instances, runs `converge` (your role), `idempotence` (second run must report no changes), and `verify` (assertions with Ansible, Testinfra or other), then destroys the instances. I describe it from its documentation and did not run it. The test strategy it embodies is exactly the one you can build with `pytest` and `subprocess`.

## Rung 4: assertions about the result

Check the state, not just the exit code:

```yaml
- name: Verify config
  ansible.builtin.stat: {path: /etc/app/app.conf}
  register: st
- ansible.builtin.assert:
    that: [st.stat.exists, st.stat.mode == "0644"]
```

Put such verification tasks in a separate playbook (`verify.yml`) so they can be run against production as a read-only audit (Level 4 · 06), or use a dedicated testing library to check ports, services and packages.

## Rung 5: negative tests

Test that invalid input fails and that failure is clean. In the role project, `webapp_port=70000` and `webapp_workers=0` both failed before changing anything (the sandbox directory did not exist afterwards). Test the guard rails; they are the most valuable and least exercised code.

## Test the right thing at the right cost

| Rung | Catches | Time | Needs |
|---|---|---|---|
| Syntax check | YAML/structure | ms | nothing |
| Lint | Style, risky patterns, FQCN, naming | seconds | ansible-lint |
| Check mode on real hosts | Drift, wrong values | seconds-minutes | a target |
| Converge + idempotence | Non-idempotent tasks, ordering | minutes | disposable target |
| Verify assertions | Wrong end state | minutes | disposable target |
| Integration across roles/hosts | Cross-host ordering, real services | many minutes | VMs / test fleet |

Run the cheap rungs on every commit and the expensive ones on pull requests or nightly. A common trap is skipping the expensive rungs because they are slow; keep one fast converge+idempotence test per role and let the slow ones run less often.

## Testing the playbooks that call roles

Test roles in isolation (each role with its own converge playbook and tests) and the integrated playbook in a staging environment. For variables, test the defaults and each documented override. For templates, render them in a test and compare the output to a golden file where the output is stable.

## How It Actually Works

`ansible-lint` loads each file with Ansible's own parsers (so it needs a working Ansible install), builds a normalised representation of plays, tasks and roles, and runs each rule class over it. Rules are Python classes tagged with identifiers (`fqcn[action-core]`, `no-changed-when`); the profile is a set of rules that must pass. Because it uses the real parser it sees through includes and imports to some extent, but it cannot evaluate templates or know variable values. The dynamic tests rely on the contract of modules (Level 1 · 05): a module reports `changed: false` when no change was needed, so `changed=0` in the recap is a machine-checkable statement about convergence. That contract is also the limit of the test: a module that lies about `changed` makes the test meaningless, which is why `changed_when` on commands matters.

## Common mistakes

- **No lint at all**, or lint with half the rules turned off and no record why.
- **Unpinned lint version** whose new rules break builds without a code change.
- **Testing only on the first run.**
- **Treating a container test as proof** for service or kernel behaviour.
- **Tests that share state** across cases.
- **No negative tests** for input validation.
- **Never running the verify step against production** as a read-only audit.

## Exercise

1. Run `ansible-lint` on one of your playbooks and fix everything until it passes the `production` profile. Note which rule took longest to satisfy.
2. Write a `pytest` that applies a role twice in a temporary directory and asserts `changed=0` the second time, then add a check-mode assertion.
3. Add a negative test that proves an invalid variable value fails before any change.
4. Draft a CI job for a roles repository: which rungs run on every push, which nightly, and what environment each needs.
