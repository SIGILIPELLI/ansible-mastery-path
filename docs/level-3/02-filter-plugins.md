---
description: "Custom filter and lookup plugins: writing, registering and testing filters, a lookup that runs on the controller, and the default comma-join surprise."
---

# 02 · Filter and Lookup Plugins

Filters transform data inside Jinja2 expressions. Lookups fetch data from outside the play (a file, an environment variable, a secrets store). Both run on the **controller**, and both are pure Python, which makes them far easier to unit-test than a long Jinja expression.

!!! note "What was run"
    Three filters (`human_bytes`, `kv_to_dict`, `mask_secrets`) and one lookup (`envfile`) were written in `src/l3`, loaded with `ANSIBLE_FILTER_PLUGINS` / `ANSIBLE_LOOKUP_PLUGINS`, and exercised in a playbook and in pytest (23 tests across plugins and inventory, all passing after two corrections described below). They were not packaged in a collection.

## Filter plugins

A filter plugin is a Python file with a `FilterModule` class whose `filters()` method returns a dictionary of names to callables:

```python
def human_bytes(value, base=1024):
    n = float(value) ...
    return "1.5 KiB"

class FilterModule(object):
    def filters(self):
        return {"human_bytes": human_bytes, "kv_to_dict": kv_to_dict, "mask_secrets": mask_secrets}
```

Put it in `filter_plugins/` next to the playbook or inside a role/collection. Results from a real playbook:

```text
sizes:  [0 B, 1023 B, 1.0 KiB, 1.5 KiB, 5.0 GiB]       # [0, 1023, 1024, 1536, 5368709120] | map('human_bytes')
kv:     {a: "1", b: "two"}                              # 'a=1\n# c\nb = two' | kv_to_dict
masked: {user: u, db_password: "********", nested: {api_token: "********", ok: 1}}
```

Errors should be `AnsibleFilterError` with a clear message; Ansible adds the task location. `-5 | human_bytes` produced `The filter plugin 'human_bytes' failed: human_bytes expects a non-negative number, got -5`.

Design points:

- **Make filters pure** (no I/O, no global state). They then compose, cache, and test trivially.
- **Return native types** (dict, list) not strings that need re-parsing.
- **Validate input types** and raise `AnsibleFilterError` instead of a Python traceback.
- **Don't mutate arguments.** `mask_secrets` returns a copy (a test asserts the original is unchanged).
- **Document** with a `DOCUMENTATION` block when shipping in a collection (`plugins/filter/x.py` plus a `.yml` doc file in recent versions).

`mask_secrets` is worth a comment: it masks values whose **keys** look sensitive (`password`, `secret`, `token`, `key`), recursing through dictionaries and lists. It is a convenience for logging, not a security control: a secret under an innocently named key (`data`) is not masked. Use `no_log: true` for real protection (Level 2 · 05).

## Why a filter instead of Jinja

`kv_to_dict` could be done with `split`, `map` and `dict`, but the Jinja version is unreadable and untestable. As a plugin it has ten pytest cases: comments, blank lines, spaces around `=`, values that contain `=` (`u=http://x?a=b` keeps everything after the first `=`), and a clear error for a line with no `=`. A rule of thumb: when an expression needs more than one level of nesting or more than a line, move it to a plugin.

## Lookup plugins

A lookup runs on the controller and returns a list. `lookup('envfile', 'DB_HOST', 'DB_PASS', file='app.env')` reads a dotenv-style file there:

```python
class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)
        path = self.get_option("file")
        ... parse the file ...
        for key in terms: out.append(data[key]) or default or raise AnsibleLookupError
        return out
```

with `DOCUMENTATION` declaring the options (`file` required; `default` optional) so `set_options`/`get_option` validate them. Results:

```text
lookup('envfile', 'DB_HOST', 'DB_PASS', file='app.env')       -> "10.0.2.21,s3cret"     (one STRING)
lookup('envfile', 'NOPE', file='app.env', default='fallback') -> "fallback"
lookup('envfile', 'NOPE', file='app.env')                      -> "The lookup plugin 'envfile' failed: envfile: key 'NOPE' not in .../app.env"
```

### The comma-join surprise

The first line is the gotcha I hit: I expected a list of two values and got the string `10.0.2.21,s3cret`. By default `lookup()` joins multiple results with commas into a single string (a legacy of `with_*` loops). To get a list, use `wantlist=True` (the test checks `"1"` and `"two"` come back separately and the comma form disappears) or the `query()` function (`query('envfile', ...)`), which always returns a list. A value that contains a comma would then be indistinguishable from two values if you took the default form. The fix is to always use `query()` or `wantlist=True` when you want a list.

### Lookups run on the controller

`lookup('file', 'x')`, `lookup('env', 'HOME')`, and my `envfile` all read **the controller's** files and environment, not the target's. A frequent bug is expecting `lookup('file', '/etc/hosts')` to read the remote machine. To read data on the target, use a module (`slurp`, `command`, `stat`) and `register`. Another consequence: a lookup runs once per templating of the expression, so an expensive lookup (an API call) repeated in a loop is slow; cache with `set_fact` or `run_once`.

Secrets and lookups: `lookup('ansible.builtin.env', 'API_KEY')` is a common way to inject CI secrets without writing them to a file. Combine with `no_log: true`. Lookups to secret managers exist in collections (not run here).

## Loading and precedence

Plugin directories are searched in this order: those set by environment/config (`ANSIBLE_FILTER_PLUGINS`), the playbook-adjacent `filter_plugins/`, role-local directories, then collections by FQCN, then built-ins. A plugin with the same name as a built-in can shadow it; prefer unique names, or give yours a collection namespace (`mycompany.platform.human_bytes`) so there is no ambiguity.

## Testing plugins

Filter functions are ordinary functions: parametrised pytest cases cover them (six `human_bytes` cases including exactly 1024 and a decimal base, three invalid inputs, `kv_to_dict` edge cases, nested masking, non-mutation). Importing a plugin file needs `ansible-core` importable for `AnsibleFilterError`, so the test module skips itself if it is missing. Lookups need a bit more: instantiate `LookupModule` and call `run` with a minimal stub, or (as I did) run `ansible localhost -m debug -a "msg={{ lookup(...) }}"` in a subprocess and assert on the output, which tests the real loading path.

## How It Actually Works

At start-up, the plugin loader builds a registry per plugin type by scanning the search paths. For filters it imports each file and calls `FilterModule().filters()`, registering the returned names (and, for collections, the fully qualified names). During templating Ansible adds those callables to the Jinja2 environment's `filters` mapping, so `{{ x | human_bytes }}` is a plain Python call of your function with `x` as the first argument. Lookups are registered the same way but exposed as the `lookup()` and `query()` functions; a lookup receives the terms and keyword options from the template, plus the current variables, and its return is wrapped as a list (and joined into a string unless `wantlist` is set). Both run in the controller's worker process, so a crashing plugin shows up as a task failure with the plugin name in the message.

## Common mistakes

- **Expecting a list from `lookup()`** without `wantlist=True`.
- **Expecting `lookup()` to read the target.**
- **Filters with side effects** or hidden state.
- **Tracebacks instead of `AnsibleFilterError`.**
- **Names that shadow built-ins.**
- **Long Jinja instead of a tested plugin.**
- **Treating `mask_secrets` as security.**

## Exercise

1. Write a filter `chunk(list, n)` that splits a list into lists of at most `n`, with tests for empty lists, exact multiples and invalid `n`.
2. Write a lookup `lastline` that returns the last non-blank line of a controller-side file; test with `wantlist` and without.
3. Demonstrate with a playbook that `lookup('file', ...)` reads the controller by creating different files on controller and target (use two `connection: local` hosts in different directories) and explaining the outcome.
4. Move a long Jinja expression from one of your templates into a filter and test it.
