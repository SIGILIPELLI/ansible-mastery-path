---
description: "Ansible Vault with real encryption: encrypt files and strings, rekey, wrong-password failures, no_log, vault IDs, and what Vault does not protect."
---

# 05 · Ansible Vault and Secrets

Playbooks need secrets: database passwords, API tokens, private keys. Committing them in plain text is a breach waiting to happen. **Ansible Vault** encrypts files or individual values so they can live in version control, and decrypts them in memory at run time.

!!! note "What was run"
    Every command below was run with `ansible-vault` and `ansible-playbook` from ansible-core 2.21.5, with real encryption. The passwords used (`correct-horse`) and secrets (`s3cr3t-value`) are throwaway examples. External secret managers (HashiCorp Vault, cloud KMS) were not used; Level 4 · 03 describes them.

## Encrypting a file

```text
$ ansible-vault encrypt secrets.yml --vault-password-file .pw
$ head -c 120 secrets.yml
$ANSIBLE_VAULT;1.1;AES256
66356235386462613565353263663334363165303233323565616465323762383430316330313338
...
$ ansible-vault view secrets.yml --vault-password-file .pw
db_password: s3cr3t-value
api_key: abc123
```

The file now starts with a header (`$ANSIBLE_VAULT;1.1;AES256`) followed by hex-encoded ciphertext, 7 lines for this two-line file. It is safe to commit. `view` decrypts to the terminal; `edit` opens it in `$EDITOR` and re-encrypts on save; `decrypt` writes plain text (careful: it overwrites the file unless you use `--output`). The documented cipher is AES-256 in counter mode with an HMAC for integrity, with a key derived from your password by PBKDF2 and a random salt; I did not audit this and describe it from the documentation.

**Same plaintext, different ciphertext.** Encrypting the identical content twice with the same password gave different files (I compared them with `cmp`). The random salt means you cannot tell whether two secrets are equal, and that **every re-encryption is a full-file change in Git**, even when only one value changed: reviewing a vaulted file's diff tells you nothing about what changed. Convention: keep vaulted files small and separate from non-secret variables.

## Wrong or missing password

- No vault secret supplied when a play needs one: `Invalid vars_files file ...: Attempting to decrypt but no vault secrets found.` and the play does not start.
- A wrong password: `Decryption failed (no vault secrets were found that could decrypt)`.
- Rekeying changes the password without changing contents: `ansible-vault rekey a.yml --vault-password-file .pw --new-vault-password-file .bad` printed `Rekey successful`, and the file then opened only with the new password.

Note that vault errors happen at load time, so a missing password is caught immediately, before any host is touched.

## Encrypting a single value

Instead of encrypting a whole file you can embed an encrypted value in a normal variables file:

```text
$ ansible-vault encrypt_string 's3cr3t-value' --name db_password --vault-password-file .pw
db_password: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          66653235626435393734656233656461...
```

This keeps non-secret variables readable and diff-friendly, and only the secret is opaque. Both styles are common. The trade-off: with `encrypt_string` the *names* of secrets are visible in the file, which can be useful (reviewers see which secrets exist) or undesirable. Many teams use the pattern `group_vars/db/vars.yml` (plain, references `db_password: "{{ vault_db_password }}"`) plus `group_vars/db/vault.yml` (encrypted, defines `vault_db_password`). That keeps variable names greppable while the values stay encrypted.

## Using vaulted data in a play

`vars_files: [a.yml]` with `--vault-password-file .pw` loaded the secret into `db_password`. Things to know, from the experiment:

- **A task that prints the variable leaks it.** `debug: msg="pw={{ db_password }}"` printed `pw=s3cr3t-value` in the output. Vault protects data **at rest**, not in output.
- **`no_log: true`** hides a task's results. A failing command with `no_log: true` printed only `{"censored": "the output has been hidden due to the fact that 'no_log: true' was specified for this result", "changed": true}`. Without `no_log`, a failing command whose arguments contain the secret would print the command line, including the secret. Put `no_log: true` on any task that handles secrets (`copy`/`template` of key material, `uri` with tokens, `user` with passwords). It also hides useful error details, so debug without it in a safe environment.
- **Secrets in `-vvv` output, `--diff` output and retained logs.** `--diff` prints file contents for `template`/`copy` unless `diff: false` or `no_log: true`.
- **Secrets on the target.** `copy` with a secret creates a file with whatever mode you give it: set `mode: "0600"` and the right owner (I did). Tools that read secrets from process arguments leak them to `ps`.
- **Check mode and handlers** do not change any of this.

## Providing the password

Options, from least to most careful:

1. `--ask-vault-pass`: prompts interactively; fine for people, impossible for CI.
2. `--vault-password-file path`: a file containing the password (keep it out of Git, mode 0600). A file that is *executable* is run and its stdout is used as the password, so you can fetch it from a secret manager or keychain.
3. The `ANSIBLE_VAULT_PASSWORD_FILE` environment variable or the config file setting.
4. In CI, a pipeline secret written to a temporary file for the run, or an executable script that reads it from the CI system's environment.

Never put the password in the repository next to the vault. Rotate it when someone with access leaves (rekey all files) and treat the vault password as the single most sensitive value.

## Vault IDs

Different secrets often need different passwords (dev vs prod). `--vault-id label@source` supports several:

```text
$ ansible-vault encrypt_string --vault-id prod@.pw 'x' --name k
k: !vault |
          $ANSIBLE_VAULT;1.2;AES256;prod
```

The header becomes version 1.2 and includes the label (`prod`), so Ansible can pick the right password among several supplied with multiple `--vault-id` options. Without labels it tries all supplied passwords in order, which is slower and ambiguous.

## What Vault does not do

- It does not hide secrets from anyone who can run the playbook with the password: they can `debug` the variable. Authorisation is controlled by who gets the password.
- It does not provide rotation, audit trails, dynamic or short-lived secrets, or per-secret access control. Those need a secrets manager (Level 4 · 03).
- It does not protect the control node's memory or logs, and the target machine sees the decrypted value.
- Git history keeps old ciphertexts. If the vault password was ever exposed, every previous version of the file is readable by the attacker, so you must change the **secrets themselves**, not just rekey.

## How It Actually Works

The vault file format is text: a header line carrying the format version, cipher and optional label, then hex of an encrypted payload that itself contains a salt, an HMAC and the ciphertext. To decrypt, Ansible derives keys from the password and salt with PBKDF2, verifies the HMAC (which is why a wrong password fails cleanly rather than yielding garbage), and decrypts. Loading a vaulted `vars_files` entry or an inline `!vault` value happens in the controller's variable loader; the decrypted text is then parsed as YAML and merged like any other variable. For `encrypt_string`, the value is stored as a custom YAML tag (`!vault`), which the loader decrypts lazily when the variable is first used. Since decryption happens on the controller, the target never sees the vault password, only the decrypted values sent to modules.

## Common mistakes

- **Committing `.vault_pass` or leaving it world-readable.**
- **Printing secrets with `debug`, `-vvv` or `--diff`.**
- **Missing `no_log`** on secret-handling tasks.
- **Rekeying after a leak** and assuming old secrets are safe.
- **Encrypting a huge file** so every change is an unreviewable diff.
- **One vault password for everything**, including dev contributors and production.
- **No procedure for rotating** the vault password and the secrets.

## Exercise

1. Encrypt a file, view it, edit it, rekey it, and confirm the old password no longer works. Commit the encrypted file to a scratch Git repository and look at the diff after changing one value.
2. Write a play that uses a vaulted variable in a `copy` with `mode: "0600"` and `no_log: true`; verify the output shows no secret even with `-v`.
3. Set up the `vars.yml` + `vault.yml` split for a database password and show that `grep -r db_password` finds the usage.
4. Write a short rotation procedure for your vault password: who is told, in what order files are rekeyed, and how you verify nothing still uses the old one.
