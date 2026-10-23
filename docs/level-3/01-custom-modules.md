---
description: "Writing a custom Ansible module in Python: argument spec, check mode, diff, exit_json and fail_json, run standalone and in a playbook, with 25 tests."
---

# 01 · Writing a Custom Module

When no module does what you need and `command` would be fragile, write a module. A module is a Python program that reads arguments, compares current and desired state, changes the system if needed, and prints a JSON result. Writing one yourself is also the best way to understand why built-in modules behave as they do.

!!! note "What was run"
    Two modules were written and run with ansible-core 2.21.5 on a Mac: `filehash` (read-only) and `kvfile` (manages `key=value` lines, Lesson 10's project). Both were exercised standalone with a JSON argument file, through `ansible-playbook`, in check and diff mode, and by 25 pytest tests (all passed on the first run). Modules in other languages, Windows (PowerShell) modules, and modules shipped in a collection were not written.

## The minimum module

```python
#!/usr/bin/python
from __future__ import annotations
from ansible.module_utils.basic import AnsibleModule
import hashlib, os

def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type="path", required=True),
            algorithm=dict(type="str", default="sha256", choices=["sha256", "sha1", "md5"]),
        ),
        supports_check_mode=True,
    )
    path = module.params["path"]
    if not os.path.isfile(path):
        module.fail_json(msg="file not found or not a regular file: %s" % path, path=path)
    digest = hashlib.new(module.params["algorithm"], open(path, "rb").read()).hexdigest()
    module.exit_json(changed=False, digest=digest, size=os.path.getsize(path), path=path)

if __name__ == "__main__":
    main()
```

Place it in a `library/` directory next to the playbook (or in a role's `library/`, or in a collection's `plugins/modules/`) and call it by name. In a playbook, with `ANSIBLE_LIBRARY=./library`:

```text
- {name: hash, filehash: {path: ".../app.conf", algorithm: sha1}, register: h}
-> "7e4a5db2c83fccbca9c1eb994cbdbbd4a51e67d3 17"        # digest and byte size
```

The pieces:

- **`AnsibleModule`** parses the arguments Ansible passes, **validates them against `argument_spec`** (types, required, choices, defaults, mutual exclusion, `required_if`), and gives you `exit_json` and `fail_json`.
- **`module.params`** is the validated dictionary.
- **`exit_json(**kwargs)`** prints the JSON result and exits; **`fail_json(msg=...)`** reports failure. Always include `changed`.
- **`supports_check_mode=True`** declares that you handle `module.check_mode` correctly (do not change anything when it is true). A module that does not declare it is *skipped* in check mode.
- **Documentation** goes in module-level strings: `DOCUMENTATION`, `EXAMPLES`, `RETURN` (YAML). `ansible-doc -M library kvfile` renders them (I ran it; the first lines show the description and options with types and defaults). Keep them accurate; `ansible-test sanity` (not run) checks them against the argument spec in the real Ansible project.

## Where the work happens

The module runs **on the target** with the target's Python. It is shipped as a self-contained bundle with its dependencies from `ansible.module_utils`. Consequences: use only the standard library and `module_utils` unless you install other libraries on the target; the module cannot read files on the controller (that is what lookups do); and Python-version differences between targets matter (use `from __future__ import annotations` and avoid very new syntax if you support old targets).

## Design rules for a good module

1. **Idempotent by construction.** Compute the desired content/state from the current state; write only if different. `kvfile` builds the new file text in memory and compares it with the old text. Returning `changed=True` only when a write is needed is what makes check mode and drift audits honest.
2. **Pure core, thin shell.** Put the decision logic in a pure function (`kvfile.apply(lines, key, value, state)` returns the new lines and before/after values). Test it with ordinary unit tests; keep I/O in `main`.
3. **Check mode.** Compute `changed` and the diff as usual, skip the write when `module.check_mode`. In my module, `--check` on a file needing change reported `changed` and left it untouched (test passes).
4. **Diff mode.** Return `diff={"before": old, "after": new, "before_header": path, "after_header": path}`; Ansible prints it under `--diff`. Real runs showed `+workers=4` and so on.
5. **Validate input early and clearly.** `kvfile` rejects keys that are not letters/digits/underscore/dot/dash (`invalid key 'bad key'`) and values containing newlines (a newline in a value would let one setting inject another line). Fail with a message naming the problem. Do not build shell commands from user data.
6. **Use `module_utils` helpers** where they exist: `add_file_common_args=True` plus `set_fs_attributes_if_different` gives `mode`, `owner`, `group` handling and reports a mode-only difference as a change (a test confirms a mode-only change is reported and applied). `module.run_command()` runs external programs safely (no shell by default).
7. **Atomic writes.** Write to a temporary file in the same directory and `os.replace` it, so a crash never leaves a half-written file.
8. **Return useful data.** `before` and `after` let playbooks and humans see what changed.
9. **Unknown arguments are errors.** The argument spec rejects typos: a test passes `valeu` and gets `Unsupported parameters`.

## Testing a module

Three levels, all in `test_modules.py`:

1. **Unit tests of the pure function** (10 cases): add missing key; replace value; unchanged input returns the same lines; remove; absent when missing is a no-op; comments and blank lines preserved; duplicates collapsed; spaces around `=`; empty file; a key that is a prefix of another is not confused (`ab=1` vs `a`).
2. **Run the module as Ansible does**: a JSON file `{"ANSIBLE_MODULE_ARGS": {...}}` passed as `argv[1]`, executed with Python, output parsed. The tests cover create-then-idempotent, check mode leaves the file alone, diff content, mode setting, mode-only change, rejection of bad input (three parametrised cases), missing file without `create`, `absent` on a missing file, unknown argument, and `filehash` output and errors. Special keys such as `_ansible_check_mode` and `_ansible_diff` switch the modes.
3. **One real playbook run** asserting `changed=1` then `changed=0`.

Total: 25 tests, 2.6 seconds, all passed on the first run (after the code was written; I did not need to fix the tests). A fast, pure test suite like this is the reason to structure a module with a pure core.

## Common mistakes

- **Forgetting `changed`**, so results are unreliable.
- **Doing work in check mode.**
- **Not handling `exists=False` paths**, crashing with a traceback; wrap I/O and use `fail_json`.
- **Printing to stdout** other than the final JSON; stray prints corrupt the result. Use `module.debug`/`module.warn` or return data.
- **Relying on controller-side state**; the module sees the target.
- **Huge return values** (entire files); Ansible stores them in memory for every host.
- **Writing a module when a filter, lookup or role would do.** A module is for managing state on the target; formatting data is a filter's job (Lesson 02).

## Packaging

A module used by several playbooks belongs in a collection (`plugins/modules/` with the same code) with `meta/runtime.yml`, a changelog, and documentation built from `DOCUMENTATION`. Add unit tests under `tests/unit` and run `ansible-test` (not run here) for sanity and unit checks in the Ansible-supported way.

## How It Actually Works

When a task calls your module, the controller finds `library/kvfile.py`, builds an **AnsiballZ** payload (a Python zip with your file, the needed `module_utils`, and a wrapper), writes it to a temporary file on the target through the connection plugin, and executes it with the target's interpreter. The wrapper unpacks the zip, calls your `main()`, and your `AnsibleModule` reads its arguments from the wrapper's embedded JSON (when run standalone, from `argv[1]`). The final `exit_json` prints one JSON object to stdout and exits with code 0 (`fail_json` exits 1); the controller parses the last JSON object, applies keywords like `changed_when`, `failed_when` and `register`, and deletes the temporary files. Everything the module needs from Ansible for validation and file handling comes from `module_utils.basic`, which is why a module is portable across connection types.

## Exercise

1. Run `python3 -m pytest -q src/l3/test_modules.py`, then break `apply` (for example make it append duplicates) and see which tests fail first.
2. Add `backup: true` to `kvfile` that copies the old file to `path.bak` before changing it. Write the tests first, including that no backup is made when nothing changes.
3. Add `validate` (a command run on a temp file, like `copy`'s) and a test with a validator that rejects the file.
4. Write a read-only info module `portcheck` that reports whether a TCP port accepts connections (with a timeout argument) and test it with a real local socket.
