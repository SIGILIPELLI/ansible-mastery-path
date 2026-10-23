---
description: "Ansible Level 3: custom modules and plugins, dynamic inventory, command pitfalls, async, performance, rolling updates, drift and a tested custom module."
---

# Level 3 · Extending Ansible

Level 3 goes beyond using Ansible to extending and operating it: writing modules and plugins, building inventories from live sources, handling the awkward corners of `command` and `shell`, running long tasks, measuring performance, orchestrating rolling updates safely, and reasoning about state, drift and convergence.

!!! note "What was run, and what wasn't"
    **ansible-core 2.21.5** on a Mac, local connections only. Measured here: two custom modules (25 tests), three filters, a lookup and two forms of dynamic inventory (23 tests), command/shell pitfalls, async behaviour and messages, forks and fact-gathering timings on 20 local hosts, a rolling update over eight simulated servers (11 tests), and orphan/conflict/drift experiments. Not run: SSH and real network latency, pipelining, Windows and network devices (their collections were installed only to read documentation), Molecule, real cloud inventories, and Ansible's own `ansible-test`.

**Prerequisites:** Levels 1 and 2.

## Modules

1. **[Writing a Custom Module](01-custom-modules.md)**: argument spec, check and diff modes, a pure core, 25 tests.
2. **[Filter and Lookup Plugins](02-filter-plugins.md)**: and the comma-join surprise of `lookup()`.
3. **[Dynamic Inventory](03-dynamic-inventory.md)**: a script and a plugin producing identical inventories.
4. **[Command and Shell Without Breaking Idempotency](04-command-shell-pitfalls.md)**: injection, pipefail, `argv`, `creates`.
5. **[Async Tasks and Polling](05-async-polling.md)**: and the confusing message when a job outlives `async`.
6. **[Performance](06-performance.md)**: forks from 50 s to 4.5 s, and what fact gathering costs.
7. **[Rolling Updates and Failure Budgets](07-rolling-updates.md)**: and an `always:` section that defeated `max_fail_percentage`.
8. **[State, Drift and Convergence](08-state-and-drift.md)**: orphans, flip-flopping tasks, purge patterns.
9. **[Network and Windows Targets](09-network-windows.md)**: connection types and collections, read offline.
10. **[Project: A Tested Custom Module](10-project-custom-module.md)**: the capstone for the level.

## After Level 3

Level 4 is operations: controllers and execution environments, Ansible in CI/CD, secrets at scale, pull mode, Terraform together with Ansible, a drift auditor built on check mode, automation incidents, migrating scripts and anti-patterns, governance, and a capstone managing a simulated fleet.
