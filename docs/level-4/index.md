---
description: "Ansible Level 4: controllers and execution environments, CI, secrets, pull mode, Terraform, drift audit, incidents, migration, governance, capstone."
---

# Level 4 · Operating Ansible

Level 4 is about running automation as a service for a team: where playbooks execute, how they are tested in CI, how secrets are handled, when hosts pull their own configuration, how Ansible fits with Terraform, how to audit drift, how to limit and respond to incidents, how to migrate scripts, how to keep standards, and a capstone that operates a simulated fleet.

!!! note "What was run, and what wasn't"
    **ansible-core 2.21.5** and `ansible-lint` on a Mac; all fleets are simulated with local connections. Run for real: `ansible-builder create` (no image built), a six-step CI script, an executable vault password script, `ansible-pull` against a local Git repository, a drift-report callback plugin and audit tool, a `no_log` linter, a Terraform-output inventory script (on a hand-written fixture), a preflight guard, a script-to-playbook migration comparison, `ansible-lint` configuration behaviour, and a twelve-node capstone. **Not run**: AWX or Ansible Automation Platform, container builds, GitHub Actions, Terraform, secret managers, remote hosts, Windows and network targets.

**Prerequisites:** Levels 1 to 3. The CI/CD Mastery Path course is a good companion for Lessons 02, 03 and 07.

## Modules

1. **[Controllers, AWX and Execution Environments](01-automation-platform.md)**: what a controller adds; pinning with `ansible-builder`.
2. **[Ansible in CI/CD](02-ansible-in-ci.md)**: a six-step script and the non-idempotent task it caught.
3. **[Secrets and Credentials at Scale](03-secrets-at-scale.md)**: vault password scripts, a `no_log` linter and its limits.
4. **[Pull Mode and Bootstrap](04-pull-mode.md)**: `ansible-pull`, and why `--only-if-changed` does not repair drift.
5. **[Terraform and Ansible Together](05-terraform-and-ansible.md)**: division of labour and a tested output-to-inventory script.
6. **[Auditing Drift with Check Mode](06-drift-audit.md)**: a callback plugin and an audit tool with three exit codes.
7. **[Automation Incidents and Blast Radius](07-incidents.md)**: a preflight guard that failed its own first test.
8. **[Migrating Scripts and Avoiding Anti-Patterns](08-migration-antipatterns.md)**: script versus playbook, measured; 24 anti-patterns.
9. **[Governance, Review and Standards](09-governance.md)**: lint profiles, ratchets and a config result that surprised me.
10. **[Capstone: Managing a Simulated Fleet](10-capstone-fleet.md)**: detect, scope, repair narrowly, verify.

## After Level 4

You have a working model of Ansible from a single module call to fleet operations, a set of tested tools that make the ideas concrete, and a clear record of which claims were measured on ansible-core 2.21.5 and which come from documentation. The next step is to apply them to real machines.
