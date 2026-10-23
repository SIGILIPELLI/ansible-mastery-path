---
description: "Ad-hoc commands, the module system and ansible-doc: running one module on many hosts, reading module docs, and why command always reports changed."
---

# 02 · Ad-Hoc Commands, Modules and `ansible-doc`

Before writing playbooks, learn the unit they are built from. An **ad-hoc command** runs one module, once, on a set of hosts: `ansible <pattern> -i <inventory> -m <module> -a "<arguments>"`. It is the right tool for quick checks and one-off actions, and the best way to explore what a module does and returns.

!!! note "What was run"
    Run with `ansible-core 2.21.5` on macOS, hosts using `ansible_connection=local`. The facts shown therefore describe a Mac (`Darwin`), not a Linux server; module names and arguments are the same, but Linux-only modules (`apt`, `dnf`, `systemd`, `user` on some platforms) were **not run**.

## Anatomy of an ad-hoc command

```text
$ ansible web1 -i hosts.ini -m command -a "echo hello"
web1 | CHANGED | rc=0 >>
hello
```

- `web1` is the **host pattern** (a host, group, or expression; Lesson 03).
- `-i hosts.ini` selects the inventory.
- `-m command` selects the module; `-a` passes its arguments as a string.
- The output says `CHANGED`, even though all we did was print text. The `command` module cannot know whether running a command changed anything, so it **always reports changed** unless told otherwise (`changed_when:` in a playbook, or the `creates`/`removes` arguments). This one fact explains many "why does my playbook never go green" questions, measured in Lesson 05.

Useful options: `-b` (become root; not exercised here), `-f 10` (forks), `-u user`, `-k` (ask for SSH password), `--list-hosts` (show matches without running), `-o` (one line per host).

## Modules are the vocabulary

Modules are grouped by what they manage. A small, high-value set to know by name:

| Area | Modules | Notes |
|---|---|---|
| Files | `file`, `copy`, `template`, `lineinfile`, `blockinfile`, `stat`, `fetch`, `unarchive` | `stat` reads state without changing it |
| Packages | `package`, `apt`, `dnf`, `pip` | Platform-specific; not run here |
| Services | `service`, `systemd` | Linux; not run here |
| Users | `user`, `group`, `authorized_key` | |
| Commands | `command`, `shell`, `script`, `raw` | Last resort; idempotency is on you |
| Control | `debug`, `assert`, `fail`, `set_fact`, `pause`, `wait_for` | Helpers inside playbooks |
| Info | `setup` (facts), `package_facts`, `service_facts` | |

Names are best written as **fully qualified collection names** (FQCN) such as `ansible.builtin.copy`. Short names like `copy` still work for built-ins but become ambiguous once you install collections that define a module with the same short name. This course uses FQCNs throughout, and `ansible-lint` (Level 2 · 09) can enforce it.

## Reading the documentation offline

`ansible-doc` shows module documentation from the installed code, so it always matches your version:

```text
$ ansible-doc -l | wc -l          # list modules visible by default
      71
$ ansible-doc ansible.builtin.copy | head
> MODULE ansible.builtin.copy (.../ansible/modules/copy.py)
  The [ansible.builtin.copy] module copies a file or a directory structure from the local or remote machine to a
  location on the remote machine. ...
$ ansible-doc -s ansible.builtin.file    # a YAML snippet with every option
```

On this install `ansible-doc -l` listed **71** modules in `ansible-core` alone (the batteries of cloud, network and database modules live in separate collections, Level 2 · 06). `ansible-doc -s` prints a starter snippet; the full page lists each option's type, default, choices, and whether it is required, plus the **return values** that you can `register` and use. Developing the habit of reading `ansible-doc` for the exact module version you run avoids using arguments from a blog post that your version does not have.

## Facts: what the host tells you

The `setup` module gathers **facts**, data about the host. Filtering keeps output manageable:

```text
$ ansible web1 -i hosts.ini -m setup -a "filter=ansible_distribution*"
web1 | SUCCESS => {
    "ansible_facts": {
        "ansible_distribution": "MacOSX",
        "ansible_distribution_major_version": "27",
        "ansible_distribution_release": "27.0.0",
        "ansible_distribution_version": "27.0.1"
    },
    "changed": false
}
```

Facts such as `ansible_os_family` (here `Darwin`; on Linux `Debian`, `RedHat` and so on) are how playbooks branch by platform (Lesson 07). Gathering facts costs time on every host at the start of each play, and Lesson 06 (Level 3) shows how to avoid it when you do not need them.

## Ad-hoc is for exploration, playbooks are for repeatability

Reasonable ad-hoc uses: check connectivity, look at one value across a fleet (`-m setup -a filter=...`, `-m command -a "uptime"`), restart one service in an emergency, copy one file. If you run the same ad-hoc command twice, it belongs in a playbook where it is named, reviewed, and version-controlled. Conversely, an ad-hoc `command` that changes state with no record is exactly the sort of undocumented change that automation exists to eliminate.

## Return values and `changed`/`failed`

Every module returns JSON. Three keys matter on every module: `changed` (did it modify the target), `failed` (did it fail), and `msg` (human text). Additional keys are module specific: `command` returns `rc`, `stdout`, `stderr`, `delta`; `stat` returns an object describing the file; `file` returns the resulting `mode`, `owner`, `path`. The ad-hoc output you see is a pretty-printed version of that JSON; in playbooks you capture it with `register` (Lesson 07).

## How It Actually Works

The `ansible` CLI is a one-task playbook runner. It parses the pattern against the inventory, builds a play with a single task `module: args`, and executes the same task engine as `ansible-playbook`. Module lookup searches, in order, the collection namespace in the FQCN, then built-ins, then any module paths configured through `ANSIBLE_LIBRARY` or `ansible.cfg`; custom modules (Level 3 · 01) are found the same way. Arguments are templated through Jinja2 before the module runs, then validated against the module's **argument spec** on the target, which is why a misspelled option gives a precise error naming the module and the unsupported parameter rather than a silent ignore.

## Common mistakes

- **Using `command` or `shell` for something a module does** (`command: mkdir -p /x` instead of `file`).
- **Believing `CHANGED` from `command`** means the system changed.
- **Short module names** that later collide with a collection.
- **Skipping `ansible-doc`** and guessing arguments from old tutorials.
- **Relying on ad-hoc changes** that are never recorded.
- **Quoting problems** in `-a`: the whole argument string is parsed by the module, and spaces and quotes need care.

## Exercise

1. Run `ansible-doc -l` on your install and count modules. Pick one you have never used and read its examples and return values.
2. Run `ansible <host> -m setup` unfiltered once, save it to a file, and find five facts you could use to decide behaviour.
3. Run `ansible <host> -m command -a "echo hi"` twice and note the status each time. Then run it with `-a "echo hi"` replaced by the `stat` module on a file and compare the status.
4. Use `ansible-doc -s ansible.builtin.lineinfile` and write down which two arguments decide whether the module edits an existing line or adds a new one.
