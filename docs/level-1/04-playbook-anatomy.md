---
description: "Playbook anatomy: plays, hosts, tasks, module arguments, names, gather_facts, YAML pitfalls and the run order, shown by running real playbooks."
---

# 04 · Playbook Anatomy: Plays, Tasks and Modules

A playbook is a YAML list of **plays**. Each play maps a set of hosts to a list of **tasks**, executed in order. Understanding exactly what runs, in what order, and on which hosts removes most early confusion.

!!! note "What was run"
    Every playbook here was run with ansible-core 2.21.5 against `ansible_connection=local` hosts. YAML errors and messages are copied from real runs. Remote execution, SSH and privilege escalation were not exercised.

## The smallest useful playbook

```yaml
- name: Configure web servers
  hosts: web
  gather_facts: false
  vars:
    out: /tmp/demo
  tasks:
    - name: ensure dir
      ansible.builtin.file: {path: "{{ out }}", state: directory}
    - name: write config
      ansible.builtin.copy: {dest: "{{ out }}/app.conf", content: "port=8080\n"}
```

Parts, outside in:

1. **A play** is one item of the top-level list: `name`, `hosts`, and keywords such as `vars`, `gather_facts`, `become`, `tasks`, `handlers`, `roles`.
2. **`hosts:`** is an inventory pattern (Lesson 03). A play with zero matching hosts is skipped, not failed.
3. **`tasks:`** run in order; each task runs on **all hosts in the play** before the next task starts (the default `linear` strategy; Level 2 · 08 covers alternatives).
4. **A task** has an optional `name` and exactly one module with its arguments, plus keywords such as `when`, `loop`, `register`, `notify`, `tags`, `become`, `ignore_errors`.

## Always name tasks

An unnamed task prints as its module name. Named tasks make runs readable and let you use `--start-at-task`. `ansible-playbook --list-tasks` shows the plan without running it:

```text
playbook: handlers.yml
  play #1 (web1): web1	TAGS: []
    tasks:
      ensure dir	TAGS: []
      render config	TAGS: []
      second notifier of same handler	TAGS: []
```

`--list-tasks` is a good CI step too: it parses the whole playbook, including templated task names and imports, and fails on structural errors without touching a host.

## Argument styles and the YAML trap

Three equivalent ways to give module arguments:

```yaml
- ansible.builtin.copy: dest=/tmp/x content="hi"          # key=value string (legacy style)
- ansible.builtin.copy: {dest: /tmp/x, content: hi}        # inline mapping
- ansible.builtin.copy:                                    # block mapping (preferred)
    dest: /tmp/x
    content: hi
```

Use the block form. Inline mappings are compact and break easily. While preparing this course I wrote this task:

```yaml
ansible.builtin.command: {cmd: touch "{{ target }}/marker", creates: "{{ target }}/marker"}
```

and `ansible-playbook` refused with a YAML parse error pointing at column 30, hinting at the quoting problem. The `"{{ ... }}"` inside a flow mapping, followed by more text, confused the YAML parser. Rewriting as a block mapping fixed it. **Rule: a value that starts with `{{` must be quoted; inside inline `{}` prefer not to nest quotes at all.**

Other YAML traps seen constantly:

- `yes`, `no`, `on`, `off` are booleans in YAML 1.1 (Ansible's parser follows YAML 1.1 for these); quote strings you mean literally.
- Octal-looking modes: write `mode: "0644"` as a quoted string. An unquoted `0644` is parsed by YAML as a number, and what the module then does with it is easy to get wrong (the Ansible documentation advises quoting modes or using a leading zero; I did not test the unquoted form).
- A task list indented inconsistently gives errors like `did not find expected key`.

## Syntax checking

`--syntax-check` parses the playbook without connecting:

```text
$ ansible-playbook bad.yml --syntax-check
[ERROR]: YAML parsing failed: While parsing a block mapping did not find expected key.
Origin: .../bad.yml:4:4

2   tasks:
3     - debug: msg=hi
4    - debug: msg=bad
     ^ column 4
```

The message gives the file, line and column and prints the surrounding source with a caret. (The file has a task indented one space too few.) Syntax checking does **not** catch an undefined variable or a wrong module argument; those appear at run time (Lesson 09). `ansible-lint` (Level 2 · 09) finds many more problems statically.

## Run order, precisely

For one play, Ansible runs: (1) fact gathering, if enabled; (2) `pre_tasks`; (3) `roles` and `tasks`, in the order written (`roles:` run before `tasks:` unless you use `import_role`/`include_role` inside tasks); (4) notified handlers at the end of each section (`pre_tasks`, main, `post_tasks`), or earlier with `meta: flush_handlers`; (5) `post_tasks`. A playbook with several plays runs them in order, and a later play can target different hosts, which is how "configure database, then web servers, then run a smoke test from the controller" is written as one file.

## Multiple plays and `import_playbook`

```yaml
- import_playbook: db.yml
- import_playbook: web.yml
- hosts: localhost
  connection: local
  tasks:
    - ansible.builtin.uri: {url: http://web1/health}
```

`import_playbook` is resolved when the playbook is parsed, so it can be listed and checked. The final play uses `localhost` with `connection: local` to run a check from the controller, a common pattern.

## Facts at the start of a play

By default each play begins by running `setup` on every host, which costs a connection and a second or two per host. If a play does not use facts, set `gather_facts: false` (all examples in this course that don't use facts do). If it uses a few, `gather_subset` limits the work (Level 3 · 06 measures the difference).

## `become` and the user a task runs as

`become: true` runs a task with elevated privileges (`sudo` by default). It can be set per play, per task, or per role. It requires configuration on the target (a sudoers entry, or a password supplied with `-K`). It was **not exercised** here because everything ran as my own user. When you move to real servers, add `become` at the narrowest scope that works and remember that files created by tasks with `become` are owned by root unless `owner:` says otherwise.

## Check mode and diff mode

`ansible-playbook --check` asks each module to report what it *would* change without changing it; `--diff` shows the content differences for modules that support it. Lesson 05 measures both. They work only for modules that implement check mode; `command` and `shell` are skipped in check mode unless told otherwise (a `skipping:` line appears).

## How It Actually Works

When you run `ansible-playbook`, the parser loads the YAML into a tree of `Play`, `Block`, `Task` and `Handler` objects, resolving imports (static) at load time and leaving includes (dynamic) to run time. For each play it asks the strategy plugin for the next batch of (host, task) pairs. The default `linear` strategy picks one task, queues it to a worker process per host (up to `forks`), waits for all to finish, then continues. Module arguments are templated per host immediately before execution, which is why a task can use a fact discovered earlier or a value registered by a previous task but cannot reference a variable that does not yet exist. A failed host is removed from the rest of the play (its recap shows `failed=1`) while other hosts continue, unless `any_errors_fatal` is set.

## Common mistakes

- **Unquoted `{{ }}`** at the start of a value.
- **Unquoted file modes** and yes/no strings.
- **Unnamed tasks**, producing logs nobody can read.
- **Using `key=value` strings** for complex arguments.
- **Mixing tabs and spaces** (YAML forbids tabs for indentation).
- **Assuming tasks run host by host** to completion. By default all hosts run task 1, then task 2, and so on.
- **Leaving fact gathering on** when facts are not needed.

## Exercise

1. Write a three-task playbook that creates a directory, writes a file in it, and prints the file's mode with `stat` and `debug`. Run it with `--list-tasks`, `--syntax-check`, and then for real.
2. Introduce a YAML indentation error on purpose and read the message. Fix it.
3. Add a second play to the same file that runs on a different group and observe the recap.
4. Run with `-v` and `-vvv` and note what extra information each level adds for one task.
