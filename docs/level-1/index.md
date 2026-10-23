---
description: "Ansible Level 1: what Ansible is, ad-hoc commands, inventory, playbooks, idempotency, variables, loops, templates, handlers and debugging."
---

# Level 1 · Ansible Foundations

Level 1 builds the working model: how Ansible reaches hosts, how an inventory and a playbook describe them and their desired state, what idempotency means in practice, and how to read what happened. Every playbook shown with output was run with the real `ansible-playbook`.

!!! note "What was run, and what wasn't"
    **ansible-core 2.21.5** on a Mac, with all "servers" using `ansible_connection=local` and acting on sandbox directories. Not exercised: SSH, `become`, Linux packages and services, Windows and network targets, and automation controllers. Those are labelled "not run" where they come up, and drawn from docs.ansible.com as read in October 2026.

## Modules

1. **[What Ansible Is and How It Works](01-what-ansible-is.md)**: agentless push, the model, and the comparison with scripts, Terraform and agent-based tools.
2. **[Ad-Hoc Commands, Modules and ansible-doc](02-adhoc-and-docs.md)**: one module, many hosts; why `command` always says changed.
3. **[Inventory](03-inventory.md)**: INI and YAML, groups, patterns, variable merging; a pattern that matches nothing exits 0.
4. **[Playbook Anatomy](04-playbook-anatomy.md)**: plays, tasks, run order, and a YAML mistake that broke a real task.
5. **[Idempotency, Changed and Check Mode](05-idempotency.md)**: the second-run recap, `creates`, check and diff.
6. **[Variables and Facts](06-variables-facts.md)**: sources, `set_fact`, `-e` beating everything, facts and magic variables.
7. **[Conditionals, Loops and Register](07-conditionals-loops.md)**: and a boolean-string error in ansible-core 2.21.5.
8. **[Templates and Handlers](08-templates-handlers.md)**: handlers fire once; a failure can leave a stale service.
9. **[Debugging and Reading Failures](09-debugging-playbooks.md)**: error anatomy, verbosity, `assert`, `--start-at-task` pitfalls.
10. **[Project: A Verified Baseline Playbook](10-project-baseline-playbook.md)**: 8 tests that run real Ansible.

## After Level 1

Level 2 adds structure and safety: roles, a measured variable-precedence table, Jinja2 filters, error handling, Vault with real encryption, collections, tags and limits, delegation and serial batches, linting and testing, and a tested role.
