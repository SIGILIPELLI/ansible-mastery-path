---
description: "What Ansible is: agentless push automation over SSH, YAML playbooks, desired state, how it differs from scripts, Terraform and agent-based tools."
---

# 01 · What Ansible Is and How It Works

Ansible is a tool for describing the state you want a machine to be in and making it so. You write a **playbook** in YAML, point it at an **inventory** of machines, and Ansible connects to each one, runs small programs called **modules**, and reports what changed. There is nothing to install on the managed machines beyond an SSH server and Python, which is why it is called **agentless**.

!!! note "About this course and what was run"
    This course was written on a **Mac** with **ansible-core 2.21.5** installed in a Python 3.14.7 virtual environment. Every playbook that is shown with output **was run with the real `ansible-playbook`** against hosts that use `ansible_connection=local`, which means they all execute on the same laptop, and the "servers" are directories under a sandbox path. That is faithful for the playbook language, modules such as `file`, `copy`, `template`, `lineinfile`, variables, handlers, roles, vault, and the plugin APIs. It does **not** exercise: SSH connections, SSH keys and multiplexing, `become` (privilege escalation), Linux package managers and `systemd`, Windows or network devices, or a real automation controller such as AWX. Those lessons say "described, not run" and cite the Ansible documentation (docs.ansible.com) as read in October 2026. Versions and defaults change; check yours with `ansible --version`.

## The model in one picture

```text
  control node (your laptop or a CI runner)            managed nodes
  ┌────────────────────────────────────┐   SSH     ┌────────────────────┐
  │ inventory + playbook + roles        │ ───────▶ │ sshd + Python       │
  │ ansible-playbook (the only program) │          │ (no Ansible daemon) │
  └────────────────────────────────────┘          └────────────────────┘
        for each task, for each host:  copy a module, run it, collect JSON, delete it
```

Ansible is a **push** tool: the control node decides when to run and reaches out. Contrast with **pull** tools such as Puppet and Chef, where an agent on each machine periodically fetches its configuration. Push is simple to start and easy to reason about (you run it, you see the result), and it makes "run this now on exactly these hosts" natural. The cost is that nothing corrects drift between runs unless you schedule runs (Level 4 covers pull mode and scheduling).

## Declarative-ish, with an honest caveat

A task says what should be true, not how to get there:

```yaml
- name: app config directory exists with the right mode
  ansible.builtin.file:
    path: /etc/app
    state: directory
    mode: "0755"
```

If the directory already exists with that mode, the module does nothing and reports `ok`. If not, it creates or fixes it and reports `changed`. That property, **idempotency** (running it again changes nothing), is the heart of Ansible and the subject of Lesson 05. The caveat: Ansible is **not purely declarative**. A playbook is an ordered list of tasks, run top to bottom, and tasks that run arbitrary commands (`command`, `shell`) have no idea what state they leave behind. Idempotency is a property of each **module**, not of Ansible as a whole, and you can write non-idempotent playbooks easily. This course measures that rather than assuming it.

## What you actually write

| Piece | What it is | Lesson |
|---|---|---|
| **Inventory** | The hosts and groups you manage, and variables for them | 03 |
| **Playbook** | A YAML file: one or more **plays**, each mapping a set of hosts to a list of tasks | 04 |
| **Module** | The unit of work (`file`, `copy`, `template`, `user`, `package` ...) | 02 |
| **Task** | One module call with arguments, a name, and optional conditions | 04 |
| **Variables and facts** | Data from inventory, files, the command line, and information discovered on the host | 06 |
| **Handler** | A task that runs only when notified by a task that changed something | 08 |
| **Role** | A packaged directory structure of tasks, templates, defaults and handlers | Level 2 |
| **Collection** | A distribution unit for modules, roles and plugins (Galaxy) | Level 2 |
| **Vault** | Encryption for secret values in files | Level 2 |

## Ansible compared with neighbours

- **Shell scripts.** A script is a procedure; if it is run twice it may fail or duplicate work. Ansible modules check state first. Scripts are fine for one-off glue, and Ansible can run them (with care, Level 3).
- **Terraform / OpenTofu.** Terraform provisions infrastructure (networks, VMs, databases) by comparing desired and recorded **state**, with a plan step. Ansible mostly configures what runs *on* machines, keeps no state file, and discovers state by asking the host. They are commonly combined (Level 4 · 05). Ansible can create cloud resources too, but without a plan/state model you must be careful.
- **Puppet / Chef / Salt.** Agent-based, pull by default, with their own languages (Puppet DSL, Ruby, Salt YAML+Jinja). Ansible's selling point is the low barrier (YAML, SSH). The trade-offs are speed at scale (SSH-per-task is slower than local agents) and the lack of continuous enforcement out of the box.
- **Containers / immutable images.** If you replace servers rather than modify them, Ansible is used to *build* images or to bootstrap hosts, and less to patch running machines.

## A first run, for real

The smallest useful command, executed with `ansible-core 2.21.5` on the control node against itself:

```text
$ ansible web -i hosts.ini -m ping
web1 | SUCCESS => {"changed": false, "ping": "pong"}
web2 | SUCCESS => {"changed": false, "ping": "pong"}
```

`ping` here is **not** ICMP. It is the Ansible `ping` module: Ansible connected to the host, ran a small Python program, and got `pong` back as JSON. A `SUCCESS` therefore proves: the connection works, Python is usable on the target, and the module machinery works end to end. With `ansible_connection=local` the "connection" is a local subprocess, which is why this works without SSH on a laptop; on real servers you would see SSH authentication here, and most first-day failures live in this step.

## Where Ansible fits in a delivery pipeline

You typically use Ansible to (1) bootstrap a fresh machine into a known baseline, (2) configure applications and services, (3) run orchestrated changes across a fleet in a defined order (rolling updates, Level 3), and (4) audit drift with check mode (Level 4 · 06). It is the "configure" step after Terraform provisions and before the application deploy tools take over; Level 4 · 02 of the CI/CD course on this site covers running such jobs from a pipeline.

## A note on versions

Ansible is two things that are versioned separately: **ansible-core** (the engine and `ansible.builtin`) and **collections** (everything else). Behaviour changes between core versions; this course found, for example, that a `when:` on the string `"false"` is an error in 2.21.5. Pin both, and read the porting guide for your version before upgrading.

## How It Actually Works

For each task and each host (in parallel across hosts, up to `forks`, default 5), Ansible on the control node does roughly this: build the module arguments by evaluating Jinja2 templates against the host's variables; package the module code and its arguments into a temporary file; transfer it to a temporary directory on the target through the connection plugin (SSH by default; with `connection=local` it simply runs locally); execute it with the target's Python interpreter; read the JSON the module prints (`changed`, `failed`, `msg`, return data); remove the temporary files; and move to the next task. Because the module is shipped fresh for every task and each module is a self-contained program, no agent or long-lived process is needed. Optimisations such as SSH pipelining reduce the round trips (Level 3 · 06). This design explains both its main strengths (simple, nothing to maintain on targets) and its weaknesses (a task costs at least one connection round trip, so very large fleets and very long task lists get slow).

## Common mistakes

- **Treating Ansible as a script runner** and putting everything in `shell:`, losing idempotency and check mode.
- **Expecting state tracking** like Terraform. Ansible has no memory of what it did last time; it only inspects the host now.
- **Assuming every module is idempotent.** Some always report `changed` (Lesson 05).
- **Confusing the control node and the managed node.** Python on the controller and Python on the target can be different versions, and modules run on the target.
- **Using `ping` as a network test.** It tests Ansible's own connection and Python, not reachability in the ICMP sense.
- **Skipping the inventory** and running against `localhost` by accident.

## Exercise

1. Install `ansible-core` in a virtual environment (`python3 -m venv ans && ans/bin/pip install ansible-core`) and run `ansible --version`. Record the version, the Python version and where the config file is (it printed `None` here).
2. Create an inventory with one host whose connection is `local` and run `ansible all -i hosts.ini -m ping`. Then break it (point `ansible_python_interpreter` at a path that does not exist) and read the error.
3. Write down, for a server you manage, three things you do by hand that would make a good first playbook, and which module might do each.
4. In two sentences each, explain when you would choose Ansible, Terraform, and an immutable image for the same job.
