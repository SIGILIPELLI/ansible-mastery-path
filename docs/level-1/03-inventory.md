---
description: "Inventory in practice: INI and YAML formats, groups and children, host patterns, variable placement and merging, checked with ansible-inventory."
---

# 03 · Inventory: Hosts, Groups and Variables

The inventory tells Ansible **what exists**. It lists hosts, arranges them into groups, and attaches variables. A good inventory is the foundation for everything else: the same playbook runs against `staging` or `production` simply by pointing at a different inventory, and the group structure decides which tasks apply where.

!!! note "What was run"
    All output below is from the real `ansible-inventory` and `ansible` commands (ansible-core 2.21.5). Hosts use `ansible_connection=local`, so there are no real remote machines or SSH. Dynamic inventories (cloud, CMDB) are Level 3 · 03.

## Two static formats

INI (compact):

```ini
[web]
web1 ansible_connection=local http_port=8081
web2 ansible_connection=local

[db]
db1 ansible_connection=local

[prod:children]
web
db

[all:vars]
env=staging

[web:vars]
http_port=80
```

YAML (same idea, nestable, better for complex data and types):

```yaml
all:
  vars: {ansible_connection: local}
  children:
    web:
      hosts:
        web1: {http_port: 8081}
        web2:
      vars: {http_port: 80}
    db:
      hosts: {db1: }
```

Use INI for small inventories, YAML when values are lists or dictionaries (INI values are strings, with some parsing, and type surprises). The special group `all` always exists, and `ungrouped` holds hosts that are in no other group. A group can contain other groups (`:children`), so `prod` here is the union of `web` and `db`.

## Inspect before you trust

`ansible-inventory` shows how Ansible understood your files:

```text
$ ansible-inventory -i hosts.ini --graph
@all:
  |--@ungrouped:
  |--@prod:
  |  |--@web:
  |  |  |--web1
  |  |  |--web2
  |  |--@db:
  |  |  |--db1

$ ansible-inventory -i hosts.ini --host web1
{ "ansible_connection": "local", "env": "staging", "http_port": 8081, ... }
$ ansible-inventory -i hosts.ini --host web2
{ ..., "env": "staging", "http_port": 80 }
```

Two things to read here. `--graph` shows the tree, which confirms `prod` contains `web` and `db`. And `--host` shows the **merged variables** for one host: `web1` has `http_port: 8081` (set on the host) while `web2` gets `80` (from the `[web:vars]` group). A host variable beats a group variable for the same name, one rule of precedence out of many (Level 2 · 02 measures the full order). `env=staging` came from `[all:vars]` and applies to everyone. `--list` prints the whole inventory as JSON, which is also the format dynamic inventory scripts must emit.

## Host patterns

The first argument to `ansible` and the `hosts:` of a play is a **pattern**. Measured with `--list-hosts`:

| Pattern | Meaning | Matched |
|---|---|---|
| `web` | the group | web1, web2 |
| `web:db` | union | web1, web2, db1 |
| `prod:!db` | in prod but not db | web1, web2 |
| `web:&prod` | intersection | web1, web2 |
| `web1,db1` | explicit list | web1, db1 |
| `nomatch` | nothing | **0 hosts**, with a warning |

The last row matters operationally: a pattern that matches nothing prints a *warning* and does nothing, and the play **succeeds with zero hosts**. I confirmed it with a playbook whose `hosts:` was `nomatch`: it printed `skipping: no hosts matched` and exited with status **0**. A typo in a group name in a CI job can therefore pass silently. Defensive options: check `--list-hosts` in a pre-step, or fail the pipeline when the host count is zero.

## Where variables live

Ansible reads variables from many places. For inventories, the structured, version-friendly way is directories next to the inventory:

```text
inventory/
  production/
    hosts.yml
    group_vars/
      all.yml            # applies to everyone
      web.yml            # applies to the web group
    host_vars/
      web1.yml           # applies to web1 only
```

This keeps data out of the host list, lets you review changes per group, and makes it easy to keep secrets in a vaulted file (`group_vars/db/vault.yml`, Level 2 · 05). A common convention is one inventory directory per environment, with the same group names and different values; the playbooks never mention environments.

## Connection variables

Variables whose names begin with `ansible_` control **how** Ansible reaches a host: `ansible_host` (the real address if the inventory name is a label), `ansible_user`, `ansible_port`, `ansible_connection` (`ssh`, `local`, `winrm` ...), `ansible_python_interpreter`, `ansible_become`. I set `ansible_python_interpreter` to the virtual environment's Python because otherwise Ansible tries to discover an interpreter on the target, a documented step that can pick a different Python than you expect. On real servers, pin the interpreter explicitly when the system has several.

## Design advice

- **Group by role and by environment**, not by one dimension: `web`, `db`, `staging`, `production`, `eu`. A host belongs to several groups, and `web:&production` selects the intersection.
- **Keep names stable** and put the real address in `ansible_host`.
- **Prefer inventory-supplied data over hard-coded values** in playbooks.
- **Don't encode behaviour in group names that nobody documents**; a short README beside the inventory pays off.
- **Test the shape**: a small script can assert that every host is in exactly one environment group; this course's pipeline (Level 4) uses `ansible-inventory --list` as the data source for such checks.

## How It Actually Works

On start-up, Ansible loads each inventory source through **inventory plugins**: `ini`, `yaml`, `script` (executable returning JSON), and others such as cloud plugins. Each plugin adds hosts and groups to an in-memory structure. Then Ansible loads `group_vars/` and `host_vars/` files that sit next to the inventory source or the playbook, and merges variables per host according to precedence rules. Merging is per variable name, with later and more specific sources winning, and dictionaries are replaced by default, not deep-merged (a setting, `hash_behaviour`, exists but is discouraged). When the play runs, `hosts:` is evaluated as a pattern against this structure to produce the **play's host list**, and each host's merged variables are what templates and conditions see.

## Common mistakes

- **Pattern matching nothing** and a green run that did nothing.
- **Variables on the wrong level**, so a host variable overrides what you thought was a group default.
- **INI type surprises**: `enabled=false` is a string unless parsed as a boolean by the consumer.
- **Putting secrets in plain inventory** files committed to Git.
- **Reusing group names with different meanings** across environments.
- **Forgetting `all:vars`** is the lowest-precedence group source, not a global override.
- **Using IP addresses as inventory names**, making renames painful.

## Exercise

1. Create the INI inventory above, run `ansible-inventory --graph` and `--host` for each host, and predict `http_port` for each before you look.
2. Convert it to YAML and confirm the graph output is identical apart from `prod`. Why might you add `prod` there too?
3. Add a `group_vars/web.yml` file with `http_port: 8000` next to the inventory and see which value `web2` gets now. (I measured it: `web2` went from 80 to **8000**, while `web1` stayed at 8081. A `group_vars` file next to the inventory beats a `[web:vars]` section inside the inventory file, and the host-level value still beats both.) Explain why that ordering is useful.
4. Write a one-line command that fails (non-zero exit) when a pattern matches zero hosts.
