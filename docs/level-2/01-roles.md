---
description: "Roles: directory layout, defaults versus vars, handlers, role parameters, validation, import versus include, and a run showing a shared-path race."
---

# 01 · Roles: Reusable Structure

A role packages everything needed to configure one thing (tasks, default variables, templates, files, handlers, metadata) into a directory with a known layout, so playbooks can say `roles: [webapp]` instead of repeating thirty tasks. Roles are the unit of reuse and sharing in Ansible.

!!! note "What was run"
    The role in this lesson (`src/l2/roles/webapp`) was created with `ansible-galaxy role init --offline` and run with ansible-core 2.21.5 against two local hosts. `ansible-lint` (production profile) passes on the final version. Shared roles from Galaxy and role dependencies on remote hosts were not exercised.

## The standard layout

```text
$ ansible-galaxy role init --offline webapp
webapp/README.md
webapp/defaults/main.yml   # low-precedence variables: the role's public interface
webapp/handlers/main.yml
webapp/meta/main.yml       # author, license, platforms, dependencies
webapp/tasks/main.yml      # entry point
webapp/tests/...           # scaffold only; replace with real tests (Lesson 09)
webapp/vars/main.yml       # high-precedence variables: internal constants
```

Other directories you add as needed: `templates/` (Jinja2 files for `template`), `files/` (static files for `copy`), `library/` (custom modules private to the role), `filter_plugins/`, and `tasks/` can contain many files that `main.yml` includes.

The key design decision is **defaults versus vars**:

- `defaults/main.yml` holds the variables a user is **meant to override**. They have the *lowest* precedence of all, so inventory, play variables or the command line win. This file is the role's documented interface.
- `vars/main.yml` holds internal constants. They have *high* precedence. But note what I measured: a **role parameter** (a variable passed in the `roles:` entry) still beat `vars/main.yml` (Lesson 02), so `vars/` is not a way to forbid overriding. Prefix internal names with `_rolename_` as a convention and do not rely on precedence for protection.

## The role used in this lesson

`defaults/main.yml`:

```yaml
webapp_port: 8080
webapp_root: "/private/tmp/.../webapp/{{ inventory_hostname }}"
webapp_workers: 2
```

`tasks/main.yml` validates input, creates a directory, renders a config, and notifies a handler:

```yaml
- name: Validate inputs
  ansible.builtin.assert:
    that:
      - webapp_port | int > 0
      - webapp_port | int < 65536
      - webapp_workers | int >= 1
    fail_msg: "webapp_port must be 1-65535 and webapp_workers >= 1"
    quiet: true
- name: Create directory
  ansible.builtin.file: {path: "{{ webapp_root }}", state: directory, mode: "0755"}
- name: Render config
  ansible.builtin.template: {src: webapp.conf.j2, dest: "{{ webapp_root }}/webapp.conf", mode: "{{ webapp_config_mode }}"}
  notify: Reload webapp
```

Used in a play with a role parameter:

```yaml
- hosts: web
  roles:
    - role: webapp
      vars: {webapp_workers: 4}
```

Real output of `--list-tasks` shows role tasks prefixed with the role name: `webapp : Validate inputs`, `webapp : Create directory`, `webapp : Render config`. The inventory gave `w2` its own `webapp_port=9000`, and the rendered files were `port=8080 workers=4 host=w1` and `port=9000 workers=4 host=w2`: the role default (8080) applied to `w1`, the host variable overrode it for `w2`, and the role parameter (workers=4) applied to both.

Passing an invalid value stopped the play at the first task: `webapp_workers=0` produced `fatal: ... "webapp_port must be positive and webapp_workers >= 1"` for each host, **before any change**. Validation at the top of a role is cheap insurance, and a role that checks its inputs gives better errors than whatever breaks later.

## A bug found by running it: two hosts, one path

My first version of the role used a fixed `webapp_root` in defaults. Both hosts run on the same laptop in this course, so both rendered the same file. On the first runs the recap showed `w2` changed again and again (`changed=1` each time, while `w1` flipped), and the file contents depended on which host ran last. After changing the default to include `{{ inventory_hostname }}` in the path, three consecutive runs gave `changed=2/2`, then `0/0`, then `0/0`, as expected.

This is an artifact of the local setup, but the lesson is real: **when two hosts share a resource, their tasks race.** It happens on real fleets with NFS-mounted directories, a shared database, or a delegated task that writes one file for every host (Lesson 08). Idempotency checks, by watching `changed` on the second run, are what catch it.

## Using roles in plays

Three ways to apply a role:

1. `roles:` section of a play: static, runs before the play's `tasks`.
2. `ansible.builtin.import_role` inside `tasks`: static, role is parsed at load time; `when` applies to every task in it; tags apply to all of them.
3. `ansible.builtin.include_role`: dynamic, evaluated when reached, so it can be conditional or looped; tags and `when` apply to the include itself, and with `apply:` you can pass them down.

Prefer `roles:` for the common case. Use `include_role` when the role name or the decision to run is computed (`include_role: name="{{ item }}"` in a loop), and remember the cost: dynamic includes are invisible to `--list-tasks` until they run, and tags work differently.

## Handlers and variables across roles

A handler defined in a role is available to the whole play and runs once, however many roles notify it by name. Handlers from different roles with the same name collide (the usual advice is to prefix: `webapp : Reload` in tasks as `notify: Reload webapp`). Variables defined in a role's `defaults` and `vars` are visible to the entire play after the role loads (a known property of Ansible's variable scope), so names must be unique across roles: use a role-name prefix.

## Role dependencies

`meta/main.yml` can list `dependencies:` (other roles that run first). They are convenient but implicit: the dependency runs for every role that lists it, once per unique parameter set, which surprises people. Prefer explicit ordering in the play, or tasks that `include_role` deliberately. Collections (Lesson 06) are the modern way to share roles, modules and plugins.

## Size and shape

A role should do one thing and have a short interface. Signs a role has grown too large: more than a dozen defaults, tasks full of `when` branching for unrelated cases, a need to pass lists of lists. Split by responsibility (install, configure, harden) or into several roles composed by the playbook. Document the interface in the README: variables, defaults, examples, supported platforms.

## How It Actually Works

When a play loads a role, Ansible resolves it by searching `roles/` next to the playbook, then the paths in `roles_path` (`ANSIBLE_ROLES_PATH`, or collection namespaces), and then it merges: `defaults/main.yml` into the lowest variable layer, `vars/main.yml` into a higher one, role parameters into a still higher one, `meta` dependencies placed first, `tasks/main.yml` turned into a block of tasks, and `handlers/main.yml` appended to the play's handlers. Templates and files are looked up relative to the role first (`templates/` inside the role), which is why `src: webapp.conf.j2` resolves without a path. A role is therefore not a runtime object; it is a loading convention that expands into the same task, handler and variable structures a plain playbook would contain.

## Common mistakes

- **Putting overridable settings in `vars/`** instead of `defaults/`.
- **No input validation**, so mistakes fail late and obscurely.
- **Un-prefixed variable names** that clash between roles.
- **Hard-coded shared paths** that make hosts race.
- **Using `include_role` where a static import is clearer**, losing `--list-tasks` visibility.
- **Implicit dependencies** in `meta` that nobody remembers.
- **Roles that configure several unrelated services.**
- **No README** documenting the variables.

## Exercise

1. Run `ansible-galaxy role init --offline myrole` and fill in defaults, one task, one template and one handler. Run it twice and confirm the second recap is `changed=0`.
2. Break the role's input validation on purpose and confirm the play fails before changing anything (check the sandbox directory).
3. Create a second role that also notifies a handler named `Reload webapp` and explain what happens.
4. Rewrite a playbook of your own as a role; list which variables moved to `defaults` and which stayed internal.
