---
description: "Jinja2 filters and expressions in Ansible: map, select, combine, dict2items, regex, default, mandatory, on real data, plus a missing-collection failure."
---

# 03 · Jinja2 Filters and Expressions

Jinja2 is the expression language in templates, `when`, and every `{{ }}`. Ansible adds its own filters, tests and lookups on top. Knowing a dozen filters well lets you shape data without custom code.

!!! note "What was run"
    The expressions and outputs below were produced by one playbook (`src/l2/filters.yml`) run with ansible-core 2.21.5. Filters from collections (`ansible.utils`) were installed from Galaxy for the last section. Jinja2 runs on the **controller**, so none of this depends on the target OS.

## Data used

```yaml
servers: [{name: a, port: 80, tags: [x, y]}, {name: b, port: 8080, tags: [y]}, {name: c, port: 443, tags: []}]
base: {a: 1, b: {c: 2, d: 3}}
over: {b: {c: 9}, e: 5}
csv: "web1, web2 ,db1"
```

## Lists of dictionaries

| Expression | Result |
|---|---|
| `servers \| map(attribute='name') \| list` | `[a, b, c]` |
| `servers \| map(attribute='name') \| join(',')` | `a,b,c` |
| `servers \| selectattr('port', 'gt', 100) \| map(attribute='name') \| list` | `[b, c]` |
| `servers \| rejectattr('tags') \| map(attribute='name') \| list` | `[c]` (empty tag list is falsy) |
| `servers \| map(attribute='tags') \| flatten \| unique \| sort` | `[x, y]` |
| `dict(names \| zip(ports))` | `{a: 80, b: 8080, c: 443}` |

`map`, `selectattr` and `rejectattr` return **generators**, so end with `| list` (or `| join`) when you need a list. `selectattr('port', 'gt', 100)` uses a Jinja test by name (`gt`, `lt`, `eq`, `in`, `match`, `defined`).

## Dictionaries

- `base | combine(over)` gives a **shallow** merge: `{a: 1, b: {c: 9}, e: 5}`; the whole `b` was replaced, and `d: 3` was lost.
- `base | combine(over, recursive=True)` gives a **deep** merge: `{a: 1, b: {c: 9, d: 3}, e: 5}`.
- `base | dict2items | map(attribute='key') | list` gives `[a, b]`; `items2dict` goes back.
- `base | to_json` printed `{"a": 1, "b": {"c": 2, "d": 3}}`; `to_nice_yaml` printed the indented YAML (4-space indentation by default in this version).

The shallow-vs-deep distinction connects to Lesson 02: variables from different layers do not merge on their own, and `combine(recursive=True)` is how you build layered settings explicitly.

## Strings and numbers

- `csv.split(',') | map('trim') | list` gives `[web1, web2, db1]`; without `trim`, `' web2 '` keeps its spaces.
- `'web-01.example.com' | regex_replace('^(\w+)-(\d+).*', '\2:\1')` gives `01:web`. Note the backslashes: in YAML double quotes they must be doubled (`'\\w'`) or the string put in single quotes.
- `'8080' | int + 1` gives `8081`; `'abc' | int(-1)` gives `-1` (the argument is the default when conversion fails).
- `'x' ~ 3` concatenates with `~` and gave `x3`; `+` on string and int would be an error. `[1,2,3] | sum` gave `6`; `7 // 2` gave `3`; `'a' if 3 > 2 else 'b'` gave `a`.

## `default` and `mandatory`

```text
'' | default('x')         -> ''     (empty string is DEFINED, so the default is not used)
'' | default('x', true)   -> 'x'    (second argument: also replace falsy values)
```

The output line was ` / x`: the first part empty, the second `x`. This catches people constantly: a variable defined as an empty string is not "undefined". Use `default(value, true)` to treat empty/false/0 as missing, and `omit` (`default(omit)`) to drop an optional module argument entirely when the variable is unset.

`mandatory` turns silent defaults into early, clear errors:

```text
{{ base.a | mandatory }}                              -> 1
{{ undefined_thing | mandatory('need undefined_thing') }}
 -> The filter plugin 'ansible.builtin.mandatory' failed: need undefined_thing
```

Use it in roles for required inputs, or use `assert` for several checks at once (Lesson 01).

## Tests

Jinja tests are used with `is`: `x is defined`, `x is none`, `x is string`, `path is file`, `r is changed`, `r is failed`, `v is version('2.0', '>=')`, `x is match('^web')`, `x is in list`. In conditions `when: x is not defined` is clearer than comparing with strings.

## Collection filters, and what happens when they are missing

IP address work lives in `ansible.utils`, not in `ansible-core`. Installed with `ansible-galaxy collection install ansible.utils -p ./collections` (it installed version 6.1.1; the filters also need the Python library `netaddr` on the controller, which I installed with pip). Then:

```text
'10.0.0.5' is ansible.utils.ip                  -> True
'10.0.0.5/24' | ansible.utils.ipaddr('network')  -> 10.0.0.0
'10.0.0.5/24' | ansible.utils.ipaddr('netmask')  -> 255.255.255.0
```

Before installation, the same expression failed with `Syntax error in template: No test named 'ansible.utils.ip'`. A filter name from a collection that is absent fails at templating time with that message, and `ignore_errors: true` let the play continue. An unknown module in a task is worse: `nosuch.collection.thing` made the **whole play** fail at load time (`couldn't resolve module/action`), before any task ran, and `ignore_errors` cannot help. Dependencies on collections belong in `requirements.yml` (Lesson 06).

## Where templating happens and its limits

All filters run on the controller, with the controller's Python. A filter that needs a library (`netaddr`, `jmespath` for `json_query`) needs it on the controller, not the target. Use `| to_json`/`from_json`, `from_yaml`, `b64encode`, `hash('sha256')`, `password_hash` (needs a library) and `quote` (shell-quote a value; use it whenever a variable goes into a `shell:` string) as needed.

Keep templates and expressions readable. When an expression gets longer than a line, compute it in a `vars:` block or a `set_fact` with a clear name, or write a small filter plugin (Level 3 · 02) which you can unit test. Long Jinja is hard to debug and impossible to unit test.

## How It Actually Works

Ansible hands each string containing `{{ }}` to a Jinja2 environment configured with Ansible's filter and test plugins (found by name through the plugin loader, including collection-qualified names such as `ansible.utils.ipaddr`). The environment compiles the expression and evaluates it against the variable context. If the whole string is a single expression, Ansible tries to convert the result back to a native type (so `"{{ 5 }}"` can produce an integer), whereas an expression embedded in surrounding text always yields a string. Errors inside a filter are wrapped as `Finalization of task args ... failed` with the original message, which is why the origin line points at the task, not the position in the expression. `undefined` values propagate as special `Undefined` objects until something uses them in a way that is not allowed; most filters then raise, while `default` explicitly handles them.

## Common mistakes

- **Forgetting `| list`** after `map`/`select`.
- **`default` with an empty string** that is defined but empty.
- **Shallow merging when you wanted deep.**
- **Unescaped backslashes** in regex strings.
- **Long expressions** nobody can read or test.
- **Using `+` between a string and a number.**
- **Filters from a collection you did not install** (or its Python dependency).
- **Unquoted variables in shell strings**; use `| quote`.

## Exercise

1. Reproduce the table with your own list of dictionaries and add `groupby` to group servers by a key.
2. Write expressions that (a) get the host with the highest port, (b) build `host:port` strings, and (c) produce a comma-separated list sorted by name.
3. Reproduce the `default('x')` versus `default('x', true)` difference and explain it.
4. Install a collection and a Python dependency from the example above, and confirm the exact error message when each is missing.
