---
description: "Ansible variable precedence measured on ansible-core 2.21.5: 14 sources ranked by experiment, with a pytest that pins the order, and the practical rules."
---

# 02 · Variable Precedence, Measured

When the same variable is defined in several places, exactly one value wins. The documentation lists the order; this lesson **measures** it on the version used for this course by setting one variable `x` in fourteen places, running a play to see which value wins, removing the winner, and repeating.

!!! note "What was run"
    `src/l2/prec/run.py` generates a fresh project for each trial (inventory, `group_vars`, `host_vars`, role, play) and runs the real `ansible-playbook` (ansible-core 2.21.5, 14 sources, 14 runs). `test_precedence.py` pins the result. The order below is **what this version did**. Precedence has been stable for years but has changed in details across releases; the documentation page "Using variables" is the reference for your version, and the test is how you notice a change.

## The method

For each trial the script writes the active sources, runs the playbook, reads the printed `X=<source name>` and records the winner. Then it drops that source from the active list and repeats until no source is left. The sources, each setting `x` to its own name:

role `defaults/main.yml`; inventory file group `[all:vars]`; inventory file group `[web:vars]`; `group_vars/all.yml`; `group_vars/web.yml`; inventory file host entry; `host_vars/h1.yml`; play `vars:`; play `vars_files:`; role `vars/main.yml`; task `vars:`; `include_vars`; `set_fact`; and `-e` extra vars.

## The result (highest first)

| Rank | Source | Notes |
|---|---|---|
| 1 | `-e` extra vars | beats everything, including `set_fact` |
| 2 | `set_fact` | |
| 3 | `include_vars` | |
| 4 | task `vars:` | |
| 5 | role `vars/main.yml` | |
| 6 | play `vars_files:` | |
| 7 | play `vars:` | |
| 8 | `host_vars/<host>.yml` | next to the inventory |
| 9 | inventory file, host entry | `h1 x=...` |
| 10 | `group_vars/web.yml` | specific group |
| 11 | `group_vars/all.yml` | |
| 12 | inventory file `[web:vars]` | |
| 13 | inventory file `[all:vars]` | |
| 14 | role `defaults/main.yml` | lowest |

Five facts from the table are worth memorising:

1. **Extra vars always win.** That makes them the operator's emergency override, and it means a value passed with `-e` can never be changed by a task.
2. **Host beats group, specific group beats `all`.** At both inventory levels (files in `host_vars`/`group_vars` and values inside the inventory file).
3. **`group_vars`/`host_vars` files beat variables inside the inventory file** at the same specificity (rank 8 versus 9, 10 versus 12 and 11 versus 13). I also saw this in Level 1: a `group_vars/web.yml` of `8000` overrode `[web:vars]`'s `80`.
4. **Role `defaults` lose to everything.** That is their purpose.
5. **Play `vars`, `vars_files` and role `vars` sit above the inventory.** Anything defined in a playbook overrides inventory data for that play, so putting settings in play `vars:` makes them hard to override per host (they win over `host_vars`!). Put defaults in the role and per-environment data in the inventory; reserve play `vars:` for values that are truly fixed for that playbook.

One more measured fact from the Level 2 role project: a **role parameter** (`roles: [{role: webapp, vars: {...}}]`) beat the role's own `vars/main.yml`. So the role's `vars/` directory is not protected from callers.

## Verifying a pairwise rule

Ranking tests are easy to misread, so the test file also checks pairs directly:

- `-e` against each of the other 13 sources: `-e` wins every time.
- host against group at both inventory levels.
- `group_vars/web.yml` against `group_vars/all.yml`: web wins.
- role defaults against each of the other 13: defaults lose every time.

These run in a few seconds each and fail with a clear diff if a future Ansible version changes the order.

## Practical rules

- **Defaults in the role, data in the inventory, overrides on the command line.** That layering matches the table: `defaults` < inventory < `-e`.
- **Do not use `set_fact` to make "defaults"**: it outranks inventory, so it silently overrides what the operator configured. Use `default()` filters or `defaults/main.yml`. Use `set_fact` for computed values.
- **Avoid play `vars:` for anything operators may want to change per host.**
- **One definition per variable where possible.** If the same variable is defined in four places, you will eventually be debugging precedence. A search for the variable name across the repository should return one definition and the places that use it.
- **Use `ansible-inventory --host name`** to see inventory-level values for a host (it shows inventory sources only, not play `vars`, role vars or facts). To see the final value a task will use, `debug: var=x` inside the play.
- **Use a prefix per role/app** (`webapp_port`) so unrelated roles don't collide.
- **Dictionaries replace, they do not merge.** If `group_vars/all.yml` sets `app: {a: 1, b: 2}` and `group_vars/web.yml` sets `app: {b: 3}`, the web value is `{b: 3}`: key `a` is gone. Merge explicitly with `combine(recursive=True)` (Lesson 03) when you want layering, e.g. `app_effective: "{{ app_defaults | combine(app_overrides, recursive=True) }}"`.

## Debugging a surprising value

1. `ansible-inventory -i inv --host h` to see inventory-derived values.
2. `ansible-playbook -vvv` to see variable files being loaded.
3. In the play: `ansible.builtin.debug: var=x`, and `var=hostvars[inventory_hostname]` to see what everything looks like for the host.
4. Bisect: comment out the suspected sources (the script above does it mechanically).
5. Search for `set_fact:` and `include_vars:` which are high in the table and often forgotten.

## How It Actually Works

Ansible's variable manager builds a dictionary per host per task by merging layers from lowest to highest priority, so later layers overwrite earlier ones by key. The layers are collected in a documented order: role defaults, inventory sources, play-level data, role vars, task/block vars, `include_vars`, `set_fact` and registered values, and finally extra vars. Group variables for several groups containing a host are merged in an order determined by the group's depth in the hierarchy (children over parents) and then alphabetically by group name, with `ansible_group_priority` available to adjust it (that last part is from the documentation; I did not test group-merge order). Lazy templating means a variable is stored as an unevaluated expression and resolved when used, so "the value of x" can depend on other variables at the time it is read, not when it was defined. This is why a variable can look defined in the file you are reading but resolve differently: a higher layer replaced it before templating.

## Common mistakes

- **Defining one variable in many places.**
- **Using `set_fact` or play `vars:` where a default is meant.**
- **Assuming dictionaries merge.**
- **Believing `vars/main.yml` protects a role from caller overrides.**
- **Debugging with `ansible-inventory` only** and missing play-level overrides.
- **Forgetting `-e` beats everything**, including in CI jobs that pass `-e` from a template.
- **Relying on an alphabetical group-merge order** instead of explicit priorities.

## Exercise

1. Run `python3 src/l2/prec/run.py` and compare with the table. Is anything different on your version?
2. Set `app: {a: 1, b: 2}` in `group_vars/all.yml` and `app: {b: 3}` in `group_vars/web.yml`; print `app` for a web host; then fix it with `combine`.
3. Write the pairwise test for one more source (for example `block vars`) and add it to the ranking.
4. Take a role you maintain, list its variables and mark each as default, internal constant, or computed, and move any that sit in the wrong layer.
