---
description: "Governance for Ansible content: review, ansible-lint profiles and ratchets, a measured config where warnings and skips still fail the build."
---

# 09 · Governance, Review and Standards

When ten people write playbooks, quality drifts unless the standards are written down and enforced by tools. Governance here means: agreed conventions, automated checks, a review process, and a way to evolve the standards without stopping work.

!!! note "What was run"
    `ansible-lint` was run with a project configuration (`.ansible-lint`) on the deliberately bad playbook from Level 2 · 09. The observed results, including one I did not predict, are quoted below. Review and organisational practices are general experience and unmeasured. No policy engine beyond ansible-lint was run.

## Standards worth writing down

A short document (one page to start) covering:

1. **Layout**: `playbooks/`, `roles/`, `inventories/<env>/`, `collections/requirements.yml`, `requirements.txt`, `ci.sh`.
2. **Naming**: plays, tasks, handlers named in sentence case starting with a capital (lint enforces `name[casing]`), roles and variables prefixed (`webapp_port`).
3. **Modules**: FQCNs always; `command`/`shell` only with justification, guards and `changed_when`.
4. **Variables**: defaults in roles, environment data in inventory, one definition each; no secrets outside Vault or the secret manager.
5. **Safety**: `no_log` on secret-handling tasks; `assert` for inputs; `serial` and `any_errors_fatal` for rolling changes; `--check --diff` before production.
6. **Testing**: lint, syntax check and a second-run idempotence test for every role and playbook; a drift check for production-relevant roles.
7. **Versions**: pinned `ansible-core`, collections and Python libraries; EE image for controller jobs.
8. **Documentation**: a README per role with variables, examples, supported platforms.
9. **Release**: roles used by many repos are tagged with semantic versions and a changelog (CI/CD course, Level 3 · 07).

Keep rules few and checkable. A rule nobody can check will be ignored; a rule with an automated check becomes habit.

## ansible-lint as the enforcer

`ansible-lint` has **profiles** of increasing strictness: `min`, `basic`, `moderate`, `safety`, `shared` and `production`. The tool prints the highest profile your content satisfies. A project config selects the target:

```yaml
---
profile: basic
warn_list:            # reported but do not fail the build
  - name[casing]
  - package-latest
skip_list:            # not checked at all
  - no-free-form
```

I ran this on the bad playbook (13 violations without a config). Result:

```text
Failed: 3 failure(s), 0 warning(s) in 1 files processed of 1 encountered.
Profile 'basic' was required, but 'min' profile passed.        exit status 2
```

Reading it: the rules in `skip_list` and `warn_list` removed some findings (down from 13), but **three findings remained** and the build still failed: the unnamed play (`name[play]`) and two unnamed tasks (`name[missing]`). I had expected my configuration to turn the run green and it did not; the rules I listed were only a subset of the problems. That is the useful behaviour for a ratchet: listing a rule is a visible decision, the remaining violations still block. The summary also shows `0 warning(s)`, so the entries in `warn_list` didn't produce counted warnings in this case; I did not investigate why (they may have been counted only when the corresponding rule matched a different category or file). Check your version's behaviour before relying on it.

Using the tool well:

- **Pin the version** (a new release adds rules). Upgrade deliberately in a branch.
- **Ratchet**: start with `basic`, record existing violations in `warn_list` with comments giving an owner and a date, and shrink the list; never grow it casually. Raise the profile when it is clean.
- **Don't blanket-skip.** Each skip is a reviewed exception with a reason, like a security exception.
- **Inline exceptions** with `# noqa: rule-id` on a line are possible and should be rare; review them like code.
- **Count and trend** violations over time as a health metric.
- **Run in CI and locally** (pre-commit hook) with the same config.

## Code review for Ansible

What a reviewer should look at:

- **Blast radius**: does this change affect more hosts than intended? Check `hosts:` and group variables.
- **Idempotency**: would a second run change anything? Did CI's second-run step pass?
- **Check-mode friendliness**: new `command`/`shell` tasks need `check_mode` and `changed_when` thought.
- **Variable precedence**: is a new variable defined in a surprising layer? Does it have a prefix?
- **Secrets**: `no_log`, Vault use, nothing printed.
- **Rollback**: if this is wrong in production, how do we undo it?
- **Orphans**: when removing a task, is there an explicit removal for existing hosts?
- **Tests**: new behaviour has a test (a negative case where input is validated).
- **Docs and changelog** for shared roles.

A pull request template with these as a checklist raises the floor. For high-risk paths (`inventories/production`, privileged roles, `sudoers`/`sshd` templates), require CODEOWNERS approval from a platform or security team (CI/CD course, Level 4 · 05 on separation of duties).

## Change management

- **Changes are pull requests**, linked to a ticket when your process requires; production applies run from a controlled pipeline or controller with an audit trail, not from laptops.
- **Plan-like preview**: attach the `--check --diff` output (Lesson 06) to the change; it is the Ansible analogue of a Terraform plan, with the caveats in that lesson.
- **Environments promote**: the same revision goes to dev, staging, then production; the variable data differs (inventories), not the code.
- **Freeze windows and break-glass** (Lesson 07): defined, rare, reviewed.
- **Emergency changes** are made through the same pipeline with an expedited review, or logged and back-ported immediately.

## Ownership and lifecycle

Every role and playbook has an owner (a team, not a person), a status (supported, deprecated), and a deprecation process: announce, give a migration path and date, remove. Shared roles are versioned; consumers pin; the owner publishes a changelog and tests supported platforms. Without owners, shared roles become communal junk drawers that nobody dares change.

## Measuring health

Useful metrics, all computable from what this course built:

- Share of playbooks passing lint at the target profile.
- Number of entries in `warn_list` and `skip_list`, and their age.
- Idempotence-test pass rate; number of tasks that change on a clean second run.
- Drift audit results: hosts drifted, tasks drifted, time to repair (Lesson 06).
- Run outcomes: failures, rollbacks, mean time to repair (CI/CD course, Level 3 · 09 for the delivery metrics).
- Share of roles with tests and READMEs.

Avoid ranking people by these; use them to find where to invest (the CI/CD course discusses how such metrics get gamed).

## Compliance as code with Ansible

Ansible can also *enforce* and *audit* compliance baselines: a role applying CIS-like settings and a check-mode run proving compliance (Level 1's baseline project is a small example). Treat third-party hardening roles like any dependency: review, pin, test, and understand what they change, since a hardening role can lock you out of a machine (disabling password login before keys are in place).

## How It Actually Works

`ansible-lint` loads each file with Ansible's parsers and produces a list of matches, each with a rule ID, tags, severity and a location. The configuration decides how each match is treated: rules in `skip_list` are not run, rules in `warn_list` are reported as warnings that do not affect the exit code, and the selected `profile` defines which rules are mandatory. The exit code is non-zero if any non-warning match remains (the observed exit status 2). Because the profile is cumulative (each profile includes the lower ones), a violation of a `min` rule such as a syntax error stops everything else, and `Profile 'basic' was required, but 'min' profile passed` simply reports the highest profile with no remaining violations.

## Common mistakes

- **Standards no tool checks.**
- **Growing skip lists silently.**
- **Unpinned lint versions.**
- **Review focused on style rather than blast radius and idempotence.**
- **No owner for shared roles.**
- **Applying production changes from personal machines.**
- **Treating a hardening role as trusted without reading it.**

## Exercise

1. Add a `.ansible-lint` to a repository at `basic`, list current violations in `warn_list` with owner and date comments, and make CI fail on anything new. Check what exit code you get.
2. Write a pull request template with the review checklist above, adapted to your estate.
3. Define three metrics for your Ansible health and write the query or script that produces each from your repos and CI history.
4. Draft the deprecation process for a shared role used in 15 repositories.
