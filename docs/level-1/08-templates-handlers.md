---
description: "Templates and handlers: Jinja2 config files, handlers that fire once on change, flush_handlers, and the case where a failure skips a handler, all run."
---

# 08 · Templates and Handlers

Configuration files are mostly the same across machines and differ in a few values. A **template** is a file with variable slots filled in with host values. A **handler** is an action (restart, reload) that should happen only if something changed. Together they implement "change the config, then reload the service, but only if the config actually changed."

!!! note "What was run"
    Real runs, ansible-core 2.21.5, local connection. The "service" is simulated by a `debug` handler and files in a sandbox; no real daemon was restarted, so service-manager behaviours (`systemd` reload semantics) were not exercised.

## Templates

A template is a Jinja2 file, by convention ending in `.j2`:

```jinja
# managed by Ansible - do not edit by hand
server {
    listen {{ http_port }};
    server_name {{ inventory_hostname }}{% if env == 'production' %}.example.com{% endif %};
{% for u in upstreams %}
    # upstream {{ loop.index }}: {{ u.name }} weight={{ u.weight | default(1) }}
{% endfor %}
}
```

Rendered for `web1` (port 8081) with `upstreams: [{name: a, weight: 3}, {name: b}]` it produced the config with comments for each upstream; with `upstreams: [{name: a}]` on a later run:

```text
# managed by Ansible - do not edit by hand
server {
    listen 8081;
    server_name web1;
    # upstream 1: a weight=1
}
```

Jinja2 tools you need: `{{ expr }}` prints a value; `{% if %}...{% endif %}` and `{% for %}...{% endfor %}` control flow; `{# comment #}`; filters (`| default`, `| upper`, `| join(',')`, `| to_nice_json`, Level 2 · 03); `loop.index`, `loop.first`, `loop.last` inside loops. Control lines such as `{% for %}` leave blank lines unless trimmed: Ansible's `template` module enables `trim_blocks` by default, which removes the newline after a block tag (this is why the output above has no blank lines), and `lstrip_blocks` can be set per task.

Good habits:

- Put a **managed-by header** so people know hand edits will be reverted.
- Keep logic out of templates where you can. Compute lists and flags in variables, and let the template format them.
- Quote values the target format needs quoted; Jinja does no escaping for config languages.
- Use the `validate:` argument of `template` and `copy` to check a file before it replaces the live one (`validate: nginx -t -c %s`); the module runs the command on a temporary file and aborts if it fails, so a bad render cannot break a running service. Not exercised here.
- Set `mode`, `owner`, `group`, and consider `backup: true` for important files.

## Templates and idempotency

`template` renders on the controller, then compares the rendered content's checksum with the destination, exactly like `copy`. The second run reported `ok`, no change. Anything that varies between renders defeats this: `{{ ansible_date_time.iso8601 }}` in a template makes every run `changed`. If you need to record a time, use a value that changes only when the config really changes (a version variable).

## Handlers

Handlers are tasks in a `handlers:` section, triggered with `notify:`:

```yaml
tasks:
  - name: render config
    ansible.builtin.template: {src: templates/nginx.conf.j2, dest: /tmp/web/site.conf}
    notify: reload service
  - name: second notifier of same handler
    ansible.builtin.copy: {dest: /tmp/web/extra.conf, content: "x=1\n"}
    notify: reload service
handlers:
  - name: reload service
    ansible.builtin.debug: {msg: "RELOAD happened"}
```

Measured over three runs:

| Run | What changed | Handler |
|---|---|---|
| 1 (fresh) | directory, site.conf, extra.conf (3 changes) | ran **once**, even though two tasks notified it |
| 2 (same inputs) | nothing | **did not run** (recap `changed=0`) |
| 3 (`upstreams` changed) | site.conf only | ran once |

The rules visible there: a handler runs only if at least one notifying task reported `changed`; it runs **once per play** no matter how many tasks notified it; it runs **after all the tasks in the play** (or section), not immediately. This is what makes "reload once at the end" cheap and safe.

Handlers can notify other handlers, can be named with `listen:` topics so one `notify: "restart web stack"` triggers several handlers, and can be flushed early:

```yaml
- ansible.builtin.meta: flush_handlers
```

Flush when a later task needs the service already reloaded (for example you start a service and then run a smoke test in the same play).

## When a failure skips the handler

```yaml
tasks:
  - name: change something
    ansible.builtin.copy: {dest: /tmp/hf.txt, content: "..."}   # reports changed
    notify: h
  - name: boom
    ansible.builtin.command: /usr/bin/false
handlers:
  - name: h
    ansible.builtin.debug: {msg: HANDLER RAN}
```

Run normally: `change something` was `changed`, `boom` failed with `rc=1`, and the handler **never ran**. The config on disk had changed but the service was not reloaded, and the next run would see no change (the file already matches), so **the handler would not fire on the next run either**. That is a real operational trap: a failed play after a config change can leave the system with new config and an old running process, and a rerun reports `ok` forever. Mitigations: `--force-handlers` (or `force_handlers: true` in the play) runs notified handlers even after a failure (with it, the output did include `RUNNING HANDLER [h]` and `HANDLER RAN`); put the notifying task last in the sequence it belongs to; or use blocks with `rescue` (Level 2 · 04); or make the handler idempotent and have a task that checks the service's actual state.

Note also the side observation in that run: the `command` task is reported `"changed": true` in the failure output. A failed `command` still says changed, consistent with Lesson 05.

## Check mode and handlers

In check mode the notifying task reports `changed` and the handler is also simulated. That makes `--check` a faithful preview of "what would restart", which operations teams use before maintenance windows.

## How It Actually Works

When a task returns `changed: true` and has `notify`, the strategy engine adds the handler's name to a per-host "notified" set. At the end of the current section (`pre_tasks`, `tasks`, or `post_tasks`) or at a `flush_handlers` meta task, the engine runs every notified handler **once**, in the order handlers are *defined* in the play (not in the order notified), and clears the set. A host that has failed is dropped from the play before the flush, which is why handlers are skipped after a failure unless `force_handlers` is on. `template` rendering happens on the controller with Jinja2 using the host's variables and then the rendered text is compared and transferred like `copy`; the `validate` step, if present, runs on the target against a temporary copy.

## Common mistakes

- **Restarting inside a task** with `command` instead of notifying a handler.
- **Expecting handlers to run immediately.**
- **Handler order assumed to follow notify order.**
- **Failure after change** leaving the service stale, with later runs showing `ok`.
- **Time-dependent templates** that change every run.
- **No `validate`** on configs that can break the service.
- **Logic-heavy templates** that nobody can test.
- **Handler names that differ by a typo** (`restart nginx` vs `Restart nginx`): a notify to a handler that does not exist is an error, but a case difference is a different handler.

## Exercise

1. Reproduce the three-run handler table. Add a third notifying task and confirm the handler still runs once.
2. Reproduce the failure case with and without `--force-handlers`. What is the state of the file and the "service" after each?
3. Add a `validate:` command to a template task that rejects any rendered file containing the word `FORBIDDEN`, and test both outcomes.
4. Write a template that renders a list of allowed IPs from a variable, one per line, and a task that makes the file unchanged when the list order changes (hint: sort in the variable or the template).
