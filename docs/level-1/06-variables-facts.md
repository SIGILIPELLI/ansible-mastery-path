---
description: "Variables and facts: where values come from, set_fact, extra vars, magic variables, dictionaries, defaults and facts, shown with real runs."
---

# 06 · Variables and Facts

Playbooks become reusable when the host-specific and environment-specific parts are variables. Ansible has a rich variable system: you define data in inventory, playbooks, files and on the command line; Ansible discovers more data as **facts**; and **magic variables** describe the run itself. This lesson shows the pieces. How conflicts are resolved (precedence) is measured in Level 2 · 02.

!!! note "What was run"
    Everything below was run with ansible-core 2.21.5 on a Mac, hosts local. Facts therefore describe macOS (`Darwin`). The `ansible_facts` dictionary has the same structure on Linux, with different values.

## Defining variables

```yaml
- hosts: web1
  gather_facts: false
  vars:
    greeting: "from play vars"
    cfg: {a: 1, b: {c: 2}}
  tasks:
    - ansible.builtin.debug: {msg: "{{ greeting }} / {{ http_port }} / {{ env }}"}
```

Output: `from play vars / 8081 / staging`. `greeting` came from the play; `http_port` (8081) from the host entry in the inventory; `env` (`staging`) from `[all:vars]`. Your task did not care where each came from, which is the point.

Common sources: inventory (host/group vars), `group_vars/` and `host_vars/` directories, `vars:` and `vars_files:` in plays, role `defaults/` and `vars/`, `set_fact` and `register` at run time, `-e` on the command line, and facts.

## Referencing and defaults

- `{{ name }}` for a simple value; `{{ cfg.b.c }}` or `{{ cfg['b']['c'] }}` for nesting (measured: `cfg.b.c=2 cfg['a']=1`). Use bracket syntax when a key contains dashes or clashes with a method name.
- `{{ missing | default('fallback') }}` gives `fallback` when `missing` is undefined. Without `default`, an undefined variable is an **error** (Lesson 09 shows the message). Defaults are how roles stay usable with minimal input.
- Strings with a leading `{{` must be quoted in YAML.
- A variable may refer to another: `url: "http://{{ host }}:{{ port }}"` is evaluated lazily when used.

## `set_fact` and its precedence

`set_fact` creates or changes a variable for the rest of the play for that host:

```text
debug greeting          -> "from play vars"
set_fact greeting       -> "set by set_fact"
debug greeting again    -> "set by set_fact"
```

It overrides play `vars` (it sits higher in precedence). But **extra vars (`-e`) beat everything**, including `set_fact`. Running with `-e greeting=CLI` printed `CLI` both before and after the `set_fact` task. That is intentional: `-e` is the operator's override, and it is also why you should never put values you want tasks to compute into variables that operators may pass with `-e`. `set_fact` values also persist across plays in the same run for that host, and with fact caching they can be cached (Level 3 · 06).

## Facts

Facts are variables Ansible discovers with the `setup` module at the start of a play when `gather_facts` is on. The full dictionary on this Mac had **90 keys** (names beginning `ansible_`). Modern style is to read them from the single dictionary `ansible_facts`, without the `ansible_` prefix:

```yaml
- ansible.builtin.debug:
    msg: "os_family={{ ansible_facts.os_family }} cpus={{ ansible_facts.processor_vcpus | default('n/a') }} py={{ ansible_facts.python_version }}"
```

printed `os_family=Darwin cpus=8 py=3.14.7`. The older injected form `ansible_os_family` pollutes the variable namespace and the Ansible documentation has been moving away from it (I did not test whether it is still injected by default in this version); prefer `ansible_facts.*`. Facts you will use constantly: `os_family`, `distribution`, `distribution_major_version`, `hostname`, `fqdn`, `default_ipv4`, `processor_vcpus`, `memtotal_mb`, `mounts`, `date_time`. Gathering them has a cost and a failure mode: if Python is missing on the target, fact gathering fails first.

**Custom (local) facts** go in `/etc/ansible/facts.d/*.fact` (INI or JSON, or an executable that prints JSON) and appear under `ansible_facts.ansible_local`. This is a way for the machine to declare its own attributes without Ansible controlling them (not run here).

## Magic variables

Ansible always provides variables about the run:

```text
host=web1  groups=['prod', 'web']  in_web=['web1', 'web2']  play_hosts=['web1']
```

- `inventory_hostname`: the name in the inventory (not necessarily the real hostname).
- `group_names`: the groups this host belongs to.
- `groups`: a dictionary of all groups to their host lists, which lets a task on one host read the whole inventory (for example to build a load balancer config from the `web` group).
- `hostvars`: a dictionary of every host's variables (`hostvars['db1'].http_port`), including facts if they were gathered.
- `ansible_play_hosts`, `ansible_play_batch`, `playbook_dir`, `role_path`, `ansible_check_mode`, `ansible_version`.

`hostvars` is powerful and risky: it couples hosts to each other and to the order of gathering. If a task reads `hostvars['db1'].ansible_facts...` and `db1` was never fact-gathered in this run, it fails.

## Variables from files and the command line

- `vars_files: [vars/common.yml]` loads a file in a play. Paths are relative to the playbook.
- `include_vars` loads at run time, including per-OS files: `include_vars: "{{ ansible_facts.os_family }}.yml"` is the classic way to handle differences between platforms.
- `-e @file.yml` or `-e '{"key": "value"}'` passes variables; JSON form keeps types (`-e port=80` passes a string that Jinja may auto-convert, but filters such as `| int` make intent explicit).

## Types and the string trap

Ansible templates return strings unless a literal type is detectable. Task arguments that are pure `{{ expr }}` are evaluated to native types where possible (a `"{{ 5 }}"` argument becomes an integer), but a value stored in a variable as a string stays a string. The "false" string is true in Python truthiness, so a condition on it would be wrong; Ansible 2.21 actually refuses it: a `when:` on a variable whose value was the string `"false"` failed with `Conditionals must have a boolean result` (Lesson 07). Use `| bool` when the value may come from the command line or an INI file.

## Naming conventions

Choose variable names that avoid collisions: prefix role variables with the role name (`nginx_port`, not `port`). Avoid names that clash with Ansible's own (`environment`, `name`, `hosts`, `ansible_*`). Keep data (what) in variables and logic (how) in tasks and templates.

## How It Actually Works

For each host and each task, Ansible builds a variable context by merging sources in a fixed priority order (Level 2 · 02 measures it), then evaluates Jinja2 expressions against that context. Facts and registered variables are stored per host in the controller's memory (and optionally in a fact cache). Because each host has its own context, two hosts running the same task can render different arguments. Templating is *lazy*: a variable that refers to another is resolved when used, so the final value can depend on facts set between the definition and the use. Jinja2 runs on the **controller**, not on the target; this is why filters and lookups are controller-side features (a lookup reads files on the controller), a distinction that matters in Level 3 · 02.

## Common mistakes

- **Undefined variables** with no `default` in roles meant to be reusable.
- **Using `set_fact` for configuration** that belongs in inventory.
- **Passing `-e` variables** and wondering why nothing else can override them.
- **Relying on injected `ansible_*` facts** instead of `ansible_facts`.
- **Reading `hostvars` of hosts that weren't gathered.**
- **Strings that should be booleans or integers.**
- **Variable names that collide** across roles.

## Exercise

1. Reproduce the `set_fact` and `-e` experiment. Predict the output of each `debug` before running.
2. Gather facts from a host and find the fact for total memory and the default IPv4 address. Write a task that prints both.
3. Use `include_vars` with a per-OS file (`Darwin.yml`, `Debian.yml`) to set a package name variable, and a `default` for unknown platforms.
4. Write a task that builds a comma-separated list of all hosts in the `web` group using `groups`.
