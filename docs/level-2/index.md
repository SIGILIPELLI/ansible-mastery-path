---
description: "Ansible Level 2: roles, measured variable precedence, Jinja2 filters, error handling, Vault, collections, tags, delegation, testing and a tested role."
---

# Level 2 · Structure and Safety

Level 1 gave you playbooks that converge. Level 2 makes them maintainable and safe to run on more than one machine: roles, a measured variable-precedence table, Jinja2 data shaping, error handling, real Vault encryption, collections as dependencies, targeted and batched runs, and testing with lint and repeated runs.

!!! note "What was run, and what wasn't"
    **ansible-core 2.21.5** and `ansible-lint` on a Mac, with all hosts local (`ansible_connection=local`). The variable-precedence order, tag and limit behaviour, serial/failure-budget results, vault commands and lint findings are measurements from those runs. Not run: SSH, `become`, real services and packages, Molecule and containers, Galaxy roles beyond installing one collection (`ansible.utils` 6.1.1), and an automation controller.

**Prerequisites:** Level 1.

## Modules

1. **[Roles](01-roles.md)**: layout, defaults versus vars, validation, and a shared-path race found by running it.
2. **[Variable Precedence, Measured](02-variable-precedence.md)**: 14 sources ranked by experiment, pinned by a test.
3. **[Jinja2 Filters and Expressions](03-jinja-filters.md)**: data shaping, `default` pitfalls, collection filters.
4. **[Blocks, Errors and Rescue](04-blocks-errors.md)**: try/rescue/always, `failed_when`, what continues after a failure.
5. **[Ansible Vault and Secrets](05-vault.md)**: real encryption, wrong passwords, `no_log`, vault IDs, limits.
6. **[Collections, Galaxy and Dependencies](06-collections.md)**: FQCNs, `requirements.yml`, pinning, missing-collection errors.
7. **[Tags, Limits and Targeting](07-tags-limits.md)**: every tag combination measured; `--limit` that matches nothing exits 1.
8. **[Delegation, Serial Batches and Strategies](08-delegation-strategies.md)**: failure budgets and `free` versus `linear`.
9. **[Testing and Linting Ansible](09-testing-ansible.md)**: 13 lint findings, idempotence tests, where Molecule fits.
10. **[Project: A Tested Role](10-project-tested-role.md)**: 9 tests, including one assumption that was wrong.

## After Level 2

Level 3 extends Ansible itself: custom modules and plugins, dynamic inventory, the pitfalls of `command` and `shell`, async tasks, performance measurements, rolling updates, drift and convergence, network and Windows targets, and a tested custom module.
