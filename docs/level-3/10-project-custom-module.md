---
description: "Level 3 project: the kvfile module with a pure core, check and diff mode, atomic writes and 25 tests, plus plugin and rolling-update suites."
---

# 10 · Project — A Tested Custom Module

This project brings Level 3 together around one deliverable: a custom module, `kvfile`, that manages `key=value` entries in a settings file. It has a pure decision function, correct check and diff behaviour, input validation, atomic writes and a thorough test suite. Around it sit the other Level 3 artefacts (plugins, dynamic inventory, rolling update), each with its own tests.

!!! note "What was run, and what wasn't"
    Everything here ran on a Mac with ansible-core 2.21.5. `kvfile` and `filehash` were executed standalone (the way Ansible runs a module: a JSON argument file), and through `ansible-playbook`. Test counts from the final run: **25** module tests (`test_modules.py`), **23** plugin and inventory tests (`test_plugins.py`), **11** rolling-update tests (`rolling/test_rollout.py`). Not done: running the module on a remote target over SSH, Windows/PowerShell versions, packaging in a collection, `ansible-test sanity`.

## Requirements for `kvfile`

1. `state: present` ensures exactly one `key=value` line for the key with the given value; `state: absent` removes it.
2. Idempotent: no change reported when the file already matches.
3. Preserve comments, blank lines and unrelated settings; collapse duplicate definitions of the managed key.
4. Check mode never writes. Diff mode returns before and after content.
5. Reject invalid keys and values containing newlines; report missing files unless `create: true`.
6. Support `mode`, `owner`, `group` and report a mode-only difference as a change.
7. Write atomically.

## Structure

- **`apply(lines, key, value, state)`**: pure; returns `(new_lines, before_value, after_value)`. Only this function decides content.
- **`main()`**: builds `AnsibleModule` with `required_if=[("state", "present", ["value"])]`, `add_file_common_args=True`, `supports_check_mode=True`; validates; reads the file; calls `apply`; computes `changed` by comparing old and new text; writes via a temp file and `os.replace` when not in check mode; applies file attributes; returns `changed`, `before`, `after`, `diff`.

Playbook run (real output) on a two-line file `# header` / `port=80`:

```text
set workers=4 (mode 0640)  -> changed
set workers=4 again        -> ok                      (idempotent)
change to 8                -> changed, before/after = 4/8
remove                     -> changed
changed flags: [True, False, True, True]
bad key "bad key"          -> failed: invalid key 'bad key'
missing value              -> failed: state is present but all of the following are missing: value
missing file, create=false -> failed: .../nofile does not exist and create=false
```

and `--check --diff` printed the `+workers=4` / `+workers=8` hunks without altering the file.

## The 25 tests

| Group | Count | Examples |
|---|---|---|
| Pure function | 11 | add, replace, unchanged returns same lines, remove, absent-when-missing no-op, comments preserved, duplicates collapsed, spaces around `=`, empty file, prefix key not confused, hash equals `hashlib` |
| Module as Ansible runs it | 13 | create-then-idempotent; check mode does not write; diff content; mode set; **mode-only change reported**; three rejected inputs (parametrised); missing file; absent on missing is a no-op; unknown argument rejected; `filehash` missing file and output |
| Real `ansible-playbook` | 1 | second run `changed=0` |

Properties the tests give you: the pure function is correct for edge cases; the module obeys the Ansible contract (JSON, `changed`, `failed`, check and diff modes); and the whole thing works through the real engine. The suite takes under three seconds because only one test starts Ansible.

### A design decision worth defending

`apply` collapses duplicates of the managed key to the first occurrence's position, and `changed` is determined by comparing complete file text. A consequence: a file with `a=1` twice is *changed* by `state: present, value: 1` because the second line is removed. That matches the requirement "exactly one line for the key" and is tested (`a=1,a=2,a=3` becomes `a=5`). A different design could treat duplicates as someone else's responsibility; the point is that the behaviour is **specified and tested**, not accidental.

## Companion artefacts and their tests

| Artefact | Tests | What they establish |
|---|---|---|
| Filter plugins (`human_bytes`, `kv_to_dict`, `mask_secrets`) | 16 | Edge cases, errors, no mutation, registration |
| Lookup plugin (`envfile`) | 2 | Reads a controller file; default join gives `1,two`, `wantlist=True` gives a list; missing key errors |
| Dynamic inventory (script and plugin) | 5 | Protocol (`--list`, `--host`, usage exit 2); the script and the plugin yield identical hosts, groups and variables |
| Rolling update | 11 | Batch sizes 1/4/3; canary failure rolls back only the canary; failure in batch 2 keeps batch 1 updated and stops batch 3; nobody left drained; re-run after a fix finishes; abort-semantics pins |

Two things went wrong on the first run of the plugin tests and are worth remembering: the plugin-sourced inventory values were wrapped in `__ansible_unsafe` in JSON output, and the lookup's default output joined results with a comma. In both cases my expectation was wrong, not the code, and the tests now pin the real behaviour with comments.

## Extending the module

1. `backup: true` creating `path.bak` before a change (tests: no backup on no-op).
2. `validate:` command, like `copy`, run on a temporary file.
3. Support `key: value` with spaces or INI sections as a separate module rather than overloading this one.
4. Return `warnings` when duplicates were collapsed.
5. A `diff` that shows only the changed lines for large files.
6. A Windows-compatible version would need a PowerShell implementation; the Python module cannot run on a target without Python.
7. Publish in a collection with `ansible-test sanity` and unit-test hooks.

## When not to write a module

Write one when you manage state on the target and need check mode, idempotency and structured results. Don't write one to: format data (a filter), fetch data from the controller side (a lookup), wrap a single command (use `command` with guards, Lesson 04), or call a REST API once (the `uri` module). The best sign you need a module is a long chain of `command`/`shell` + `register` + `changed_when` tasks that you keep copying between roles.

## How It Actually Works

Tests exploit three seams in Ansible's design. A module is a program with a documented contract (JSON in, JSON out), so it can be run without Ansible by feeding the JSON. A pure function inside the module can be imported directly. And the engine's recap and exit status are observable outputs, so end-to-end tests can assert on `changed=N`. The module's check mode works because `AnsibleModule` exposes `check_mode` from the `_ansible_check_mode` key of the arguments; the controller sets it for `--check`. File attributes use `set_fs_attributes_if_different`, which returns `True` when it changed something, folding mode changes into the same `changed` flag so users see one honest signal. The temp-file-and-rename write relies on `os.replace` being atomic on a single filesystem on POSIX.

## Common mistakes

- **Writing logic inside `main()`**, which is hard to test.
- **Doing work in check mode.**
- **Returning `changed=True` unconditionally.**
- **Not validating inputs** that reach file content or commands.
- **Tests that exercise only the happy path.**
- **Tests that start Ansible for everything**, making the suite slow.
- **Forgetting documentation**, so nobody can use the module.

## Exercise

1. Run `python3 -m pytest -q src/l3` (this runs the module, plugin and rolling tests; the rolling suite takes about 40 seconds) and read the three test files.
2. Implement `backup: true` with tests first.
3. Add `ansible-doc` text for the `mode` option and check that `ansible-doc -M library kvfile` shows it.
4. Write a short design note for a second module of your own: its arguments, its pure core, and the five tests you would write first.
