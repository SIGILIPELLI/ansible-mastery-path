---
description: "Secrets and credentials at scale: executable vault password scripts, no_log linting, secret-manager lookups, short-lived credentials and rotation, tested."
---

# 03 · Secrets and Credentials at Scale

Level 2 showed how Vault encrypts files. At scale the questions change: where does the vault password come from in CI, how do you stop people from printing secrets, how do you rotate hundreds of credentials, and when do you stop storing secrets in Git at all?

!!! note "What was run, and what wasn't"
    Run for real: an executable vault password script supplied by an environment variable (success and failure), and `nologlint.py`, a text-based linter for missing `no_log` (12 tests). **Not run**: HashiCorp Vault, cloud secret managers, SSH certificate authorities, OIDC federation or the lookups that talk to them. Their descriptions come from documentation and general practice and are marked as such.

## Where the vault password comes from

Level 2 used a password file. In CI a file is awkward, so Ansible lets `--vault-password-file` point to an **executable**: if the file is executable, Ansible runs it and reads the password from its standard output.

```python
#!/usr/bin/env python3
import os, sys
pw = os.environ.get("ANSIBLE_VAULT_CI_PASSWORD", "")
if not pw:
    print("vault_pass: ANSIBLE_VAULT_CI_PASSWORD is not set", file=sys.stderr); sys.exit(1)
print(pw)
```

Real results:

```text
with the variable set:    encrypt succeeds, playbook runs: ok=1 changed=1
without the variable:     [ERROR]: Vault password script .../vault_pass.py returned non-zero (1): None
```

and the file written by the playbook had mode `0600` (`-rw-------`). The script fails closed: a missing secret is an error, never an empty password. Replace the body to fetch from your CI secret store, a keychain, or a secret manager CLI; the interface to Ansible stays the same. Rules for the script: print only the password and a newline, send diagnostics to stderr, exit non-zero on any failure, never write the password to disk or logs, and keep the script free of the secret itself.

Multiple passwords (`--vault-id dev@dev_pass.py --vault-id prod@prod_pass.py`) let a repository hold secrets for several environments, with CI jobs for non-production given only the non-production password.

## Keeping secrets out of logs: `no_log` and a linter

Vault protects secrets at rest. At run time a secret appears as an ordinary variable and is easy to print: a `debug` task, a failing command that includes it in `cmd`, `-vvv` output, or `--diff` of a file that contains it. Level 2 · 05 measured this. The countermeasure is `no_log: true` on every task that handles a secret, and an automated check that it is there.

`nologlint.py` parses playbooks with PyYAML and flags a task when its arguments, `environment` or `vars` reference a variable whose name matches secret patterns (`password`, `passwd`, `secret`, `token`, `api_key`, `private_key`, `credential`, or a `vault_` prefix) and neither the task, an enclosing `block`, nor the play sets `no_log: true`. A `debug` task using such a variable is flagged **even with `no_log`** because the purpose of `debug` is to print. On a sample playbook:

```text
secrets/sample.yml:sample:tasks: 'leaks' uses db_password -> missing no_log
secrets/sample.yml:sample:tasks: 'prints' uses api_token -> debug prints it
2 finding(s)          (exit status 1; the task with no_log: true was not flagged)
```

12 tests cover: a plain flagged task; `no_log` on the task, on an enclosing block, and on the play clearing it; nested blocks; handlers; secrets in `environment`; the `vault_` prefix; secret names inside filter expressions (`db_password | b64encode`); non-secret names ignored; a literal word like "password policy" without `{{ }}` not flagged.

**Limits** of this heuristic, stated plainly: it works on names, so a secret stored in a variable called `data` is invisible to it; it does not follow `include_tasks` or roles into other files unless you lint them too; it flags use, not exposure through `register` (a registered result containing a secret printed later); and it cannot tell whether `no_log` hides the specific failure you need to debug. It is a net for common mistakes, not a proof.

`no_log` has its own cost: it hides the error message too (the failing task printed only `censored`). When you must debug, reproduce in a safe environment without `no_log`, or log a sanitised message yourself.

## Secrets from a secret manager (described, not run)

Instead of encrypting values into Git, fetch them at run time:

- **Lookup plugins** such as `community.hashi_vault.hashi_vault` (HashiCorp Vault), and cloud collections for AWS Secrets Manager, Azure Key Vault and GCP Secret Manager. A task reads `lookup('...', 'secret/data/app')`. Lookups run on the **controller** (Level 3 · 02), so the controller needs credentials to the secret manager, and the value is then sent to the target in the module arguments.
- **Benefits:** central rotation, access policies, audit logs, dynamic or short-lived secrets (database credentials generated per run), no ciphertext in Git history.
- **Costs:** the controller depends on the secret manager being up; the identity that fetches secrets becomes the crown jewel; and a lookup in a loop can call the API many times.
- **Combine** with `no_log`, and avoid writing the secret into files that outlive the run unless needed.

## Short-lived credentials (described, not run)

The best secret is one that expires. Options: cloud role assumption with OIDC from CI (CI/CD course, Level 1 · 08 and Level 3 · 08); **SSH certificates** signed by a CA with a short validity instead of long-lived keys on every host; database credentials issued per job; tokens limited to one scope. Ansible itself does not issue these; it consumes them from the environment or a lookup. Design so that the playbook never needs a credential that lives longer than the run.

## SSH keys and the control node

The control node's SSH private key is the master key to the estate. Practices: use an agent or a hardware-backed key; one key per environment; restrict what the key can do on targets (`authorized_keys` options, a dedicated `ansible` user with narrowly scoped `sudo`); use `ssh-agent` forwarding carefully (it lets a compromised intermediate host use your key); and rotate when people leave. Configure `host_key_checking` deliberately: disabling it removes protection against man-in-the-middle attacks and is a common shortcut that should not reach production.

## Rotation as a playbook

A rotation procedure should be automated and idempotent:

1. Generate or fetch the new secret.
2. Distribute it (update the secret manager or re-encrypt the vault file).
3. Update consumers in an order that avoids outage (accept both old and new first, then switch, then remove old).
4. Verify consumers work.
5. Revoke the old secret.
6. Record the rotation (who, when, what, evidence), not the secret.

Test the procedure on a non-production copy. Rotation is a rolling update with rollback (Level 3 · 07): do not revoke the old secret until the new one is verified everywhere.

## Handling a leak

Revoke first, investigate second (CI/CD course, Level 4 · 07). For Ansible specifically: rekeying a vault file does not help if the plaintext secret leaked; change the secret itself. Search logs and job history on the controller for the leaked value; vault-encrypted old versions in Git remain decryptable by anyone holding the old vault password.

## How It Actually Works

When `--vault-password-file` names an executable, the vault secret loader runs it with `subprocess`, captures stdout, strips the trailing newline and uses it as the password; a non-zero exit becomes the `Vault password script ... returned non-zero` error shown above. Ansible then tries the password against each encrypted blob it encounters, using the vault ID label from the header to choose among multiple secrets. `no_log` is enforced in the task executor: when a result for a `no_log` task is produced, the callback layer replaces its content with a `censored` message before any display or callback sees it, while the registered variable still holds the real data for later tasks (so a later `debug` of the registered variable still prints it unless it too is protected).

## Common mistakes

- **Vault password in the repository or in an unprotected CI variable** visible to fork builds.
- **Password scripts that fail open** (print nothing and exit 0).
- **Missing `no_log`** on tasks that handle secrets.
- **Registered variables** that hold secrets, printed later.
- **Disabling SSH host key checking** permanently.
- **Rekeying after a leak** instead of changing the secrets.
- **Long-lived shared credentials** when a short-lived alternative exists.

## Exercise

1. Write a vault password script that reads from your OS keychain or a CLI of your choice and test the success and failure paths.
2. Run `nologlint.py` on your playbooks and roles. For each finding decide fix, suppress with reason, or false positive; extend the secret-name patterns for your organisation.
3. Write the rotation playbook for one credential in your estate, in the order old-and-new, switch, verify, revoke, with a test.
4. Draw where each secret in one deployment lives at rest, in transit, in memory and in logs, and what protects it at each point.
