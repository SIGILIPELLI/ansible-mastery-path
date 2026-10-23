---
description: "Conditionals, loops and register: when expressions, loop and loop_control, retries with until, and a boolean string error found in ansible-core 2.21."
---

# 07 · Conditionals, Loops and Registered Results

Real playbooks branch (only on Debian-family hosts), repeat (create five users) and react to results (restart if the config test passed). `when`, `loop` and `register` are the three tools.

!!! note "What was run"
    Run with ansible-core 2.21.5 on macOS, hosts local, so `ansible_facts.os_family` was `Darwin` and distribution-specific branches were skipped. The error message in the "boolean strings" section is copied from a real run of this version; older versions were more lenient, so behaviour may differ on yours.

## `when`

`when` takes a Jinja2 expression (without `{{ }}`) evaluated per host:

```yaml
- name: only on Debian family
  ansible.builtin.debug: {msg: "apt would run"}
  when: ansible_facts.os_family == "Debian"
```

On the Mac this task printed `skipping: [web1]`. Combine conditions with `and`, `or`, `not`, or list them (a list means *all* must be true). Common tests: `var is defined`, `var is not none`, `result is changed`, `result is failed`, `result is skipped`, `item in list`, `version is version('2.0', '>=')`, `path is exists` (a controller-side test).

Key behaviours:

- A task skipped by `when` reports `skipping` and is **not** counted as changed.
- `when` on a task with `loop` is evaluated **per item** (below).
- A `when` on a role or `import_tasks` is applied to every task inside (and evaluated for each), unlike `include_tasks`, where the condition decides whether the include happens at all.

## Loops

```yaml
vars:
  users: [{name: ann, admin: true}, {name: bob, admin: false}, {name: cy, admin: true}]
tasks:
  - name: loop with when
    ansible.builtin.debug: {msg: "{{ item.name }} is admin"}
    loop: "{{ users }}"
    loop_control: {label: "{{ item.name }}"}
    when: item.admin
```

Actual output:

```text
ok: [web1] => (item=ann) => {"msg": "ann is admin"}
skipping: [web1] => (item=bob)
ok: [web1] => (item=cy) => {"msg": "cy is admin"}
```

`loop:` is the modern keyword (it replaced most uses of `with_items`). `item` is the current element. `loop_control` lets you rename `item` (`loop_var`, important when loops nest or when a role is called inside a loop), set a short `label` so logs do not dump big dictionaries (done above), add a `pause`, or access the index (`index_var`). Useful companions: `loop: "{{ dict | dict2items }}"` to loop over a mapping, `subelements`, `product`, and `zip` filters.

One module call can often replace a loop (`package` with a list of names installs them in one transaction, much faster than a loop that calls the package manager once per package). Loop only when the module takes a single item.

## `register`: capture the result

```yaml
- name: run per item
  ansible.builtin.command: echo {{ item }}
  loop: [one, two]
  register: res
  changed_when: false

- ansible.builtin.debug:
    msg: "{{ res.results | map(attribute='stdout') | list }} first_rc={{ res.results[0].rc }}"
```

Output: `['one', 'two'] first_rc=0`. With a loop, the registered variable has a `results` list with one entry per item, each holding the module's return values (`stdout`, `rc`, `changed`, `item`). Without a loop, the variable holds the return directly (`res.stdout`). That structural difference between looped and non-looped registers is a common source of `dict has no attribute` errors; use `ansible.builtin.debug: var=res` to look at the structure before writing expressions.

`register` works with check mode and skipped tasks: a skipped task registers a result with `skipped: true`, so conditions like `res is skipped` or `res.stdout | default('')` are needed when a later task reads it.

## `until`, `retries`, `delay`

```yaml
- name: wait until the file exists
  ansible.builtin.command: test -f /tmp/never
  register: r
  until: r.rc == 0
  retries: 2
  delay: 1
  ignore_errors: true
```

Real output: two lines `FAILED - RETRYING: ... (1 retries left)` and `(0 retries left)`, then the task failed (ignored here). The recap showed `ignored=1`. Use this pattern to wait for something asynchronous (a service answering) but prefer purpose-built modules, `wait_for` or `uri` with `until`, which give clear failures instead of retrying a generic command.

## Boolean strings: a real failure

I wrote a task with `vars: {flag: "false"}` and `when: flag`. In **ansible-core 2.21.5** the play stopped with:

```text
A 'when' expression failed: Conditional result (True) was derived from value of type 'str' ...
Conditionals must have a boolean result.
```

Older versions silently evaluated non-empty strings in various ways, which hid bugs like this one. The fix is explicit conversion: `when: flag | bool`, after which the string `"false"` converted to `false` and the task was skipped (two `skipping` lines appeared in the run). The general rule: **conditions must be real booleans.** Values from `-e` on the command line, INI inventories and environment lookups are strings until you convert them.

## Conditions on registered results

Typical patterns:

```yaml
- name: config test
  ansible.builtin.command: nginx -t
  register: test
  changed_when: false
  failed_when: false          # we want to inspect the result, not stop

- ansible.builtin.fail: {msg: "bad config: {{ test.stderr }}"}
  when: test.rc != 0
```

`failed_when: false` (or `ignore_errors: true`) lets you handle failure yourself. Prefer `failed_when` with a precise expression to a blanket `ignore_errors`, which also hides real problems such as an unreachable host or a Python exception inside the module.

## Facts-driven branching

Branch on facts, not on the group names you invented, when the difference is platform-specific:

```yaml
- ansible.builtin.include_vars: "{{ ansible_facts.os_family }}.yml"
- ansible.builtin.package: {name: "{{ web_package }}", state: present}      # name set per OS file
```

This keeps platform conditionals out of every task. Reserve `when:` for genuine behavioural differences.

## How It Actually Works

Both `when` and the loop expression are Jinja2 expressions evaluated on the controller with the host's variable context. For a looped task, the engine evaluates the loop list first, then runs the module once per item on the target (each is a separate module execution, which is why looping is slower than passing a list to a module that supports it) and evaluates `when` separately for each item with `item` set. `register` stores the aggregated result under the variable name for that host. `until` re-runs the task, re-evaluating the condition after each attempt, up to `retries`. In the release I used (2.21.5), conditionals are evaluated with strict typing, which is why the string `"false"` produced an error; I did not check in which release this started, and older versions were more lenient.

## Common mistakes

- **String booleans** in `when`.
- **`{{ }}` inside `when`**: write `when: x == 1`, not `when: "{{ x == 1 }}"`.
- **Looping package installs** one by one.
- **Forgetting that a looped `register` has `.results`.**
- **Blanket `ignore_errors`** hiding real failures.
- **Naming conflicts for `item`** in nested loops and roles; use `loop_var`.
- **Reading a skipped task's register** without a default.
- **Using `until` on a task whose failure mode is not transient.**

## Exercise

1. Reproduce the loop with `when` and add `loop_control: {index_var: i}`; print `i`.
2. Reproduce the boolean-string failure on your Ansible version and note whether it errors or warns. Then fix it two ways.
3. Register the output of a command run in a loop and print only the `stdout` values as a comma-separated string.
4. Write a retry loop that waits for a file to appear within 5 seconds, and test it by creating the file from another terminal after 2 seconds.
