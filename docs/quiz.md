---
title: "Final Quiz"
description: "Test what you have learned across all four levels of Ansible Mastery Path with a 19-question final quiz."
---

# Final Quiz

19 questions drawn from all four levels of this course. You need **70% (14 out of 19)** to pass —
you can retake it as many times as you like. Your best result is saved in this browser.

<div id="mp-quiz-root"></div>

<script type="application/json" id="mp-quiz-data">
[
  {
    "question": "A playbook reports `changed=1` on every run for this task. Why?\n```yaml\n- ansible.builtin.command: echo hi\n```\n",
    "options": [
      "The host is broken",
      "Facts weren't gathered",
      "Echo is slow",
      "command can't know state, so it reports changed every time; add changed_when: false (read-only) or creates:/guards"
    ],
    "correctIndex": 3,
    "explanation": "State-aware modules like file and copy report ok on repeat runs."
  },
  {
    "question": "Which task is idempotent?",
    "options": [
      "command: touch /etc/app/x",
      "ansible.builtin.file: {path: /etc/app, state: directory, mode: '0755'}",
      "shell: mkdir /etc/app",
      "shell: echo port=80 >> app.conf"
    ],
    "correctIndex": 1,
    "explanation": "mkdir fails when it exists, and >> appends duplicates."
  },
  {
    "question": "On a repeat run of a converged playbook, what should the recap show?",
    "options": [
      "changed equals the task count",
      "failed>0",
      "changed=0",
      "skipped=all"
    ],
    "correctIndex": 2,
    "explanation": "The recap is the instrument."
  },
  {
    "question": "`http_port` is 80 in [web:vars], 8081 on host web1, and web1 runs with `-e http_port=9000`. Which wins for web1?",
    "options": [
      "9000: extra vars beat everything",
      "8081",
      "80",
      "It errors"
    ],
    "correctIndex": 0,
    "explanation": "Host beats group and extra vars beat both (measured precedence)."
  },
  {
    "question": "A role's defaults/main.yml sets webapp_port: 8080 and a play passes webapp_port: 9000 as a role parameter. What happens?",
    "options": [
      "Both apply",
      "The role parameter overrides the default, since defaults have the lowest precedence",
      "The default wins",
      "Error"
    ],
    "correctIndex": 1,
    "explanation": "defaults are the role's public interface."
  },
  {
    "question": "`servers | selectattr('port','gt',100) | map(attribute='name') | list` with ports 80, 8080, 443 (names a, b, c) returns:",
    "options": [
      "[b, c]",
      "[]",
      "[a, b, c]",
      "[a]"
    ],
    "correctIndex": 0,
    "explanation": "Ports above 100: 8080 and 443."
  },
  {
    "question": "Shallow versus recursive combine of {a:1, b:{c:2, d:3}} with {b:{c:9}, e:5}.",
    "options": [
      "Shallow: {a:1, b:{c:9}, e:5}; recursive=True: {a:1, b:{c:9, d:3}, e:5}",
      "Both identical",
      "Shallow keeps d",
      "Recursive drops a"
    ],
    "correctIndex": 0,
    "explanation": "A plain combine replaces whole values for matching keys."
  },
  {
    "question": "A handler is notified by three tasks that each changed. How often does it run?",
    "options": [
      "Never",
      "Immediately each time",
      "Three times",
      "Once, at the end of the play"
    ],
    "correctIndex": 3,
    "explanation": "Handlers fire once per play unless flushed."
  },
  {
    "question": "A task with `when: ansible_facts.os_family == 'Debian'` runs on macOS. What's reported?",
    "options": [
      "skipping: not counted as changed (os_family is Darwin)",
      "failed",
      "changed",
      "ok"
    ],
    "correctIndex": 0,
    "explanation": "Skipped tasks aren't changed."
  },
  {
    "question": "Which structure runs a health check and rolls back on failure but always cleans up?",
    "options": [
      "block with rescue (rollback) and always (cleanup)",
      "delegate_to",
      "ignore_errors",
      "tags"
    ],
    "correctIndex": 0,
    "explanation": "Rescue runs only when the block fails; always runs regardless."
  },
  {
    "question": "What does `serial: [1, \"50%\", \"100%\"]` produce on eight hosts?",
    "options": [
      "1 batch",
      "Batches of 1, 4 and 3: a canary, then half, then the rest",
      "2 batches of 4",
      "8 batches"
    ],
    "correctIndex": 1,
    "explanation": "Verified by arithmetic: 1, then 50% of 8 = 4, then the remaining 3."
  },
  {
    "question": "An 'UNREACHABLE' error indicates what, and what's the first step?",
    "options": [
      "A lint error",
      "A connection problem (SSH, host key, network or interpreter); use -vvv and try ssh by hand",
      "A bad variable",
      "A YAML error"
    ],
    "correctIndex": 1,
    "explanation": "FAILED with rc= means the command ran and failed."
  },
  {
    "question": "`command: echo {{ user_input }}` is run with user_input 'ok; rm -rf x' under shell. How do you make it safe?",
    "options": [
      "Add -v",
      "Nothing, it's fine",
      "Use `{{ user_input | quote }}` (or avoid shell and pass argv)",
      "Use tags"
    ],
    "correctIndex": 2,
    "explanation": "The variable text is pasted into the shell line."
  },
  {
    "question": "A task removed from the playbook leaves its file on every host. Why?",
    "options": [
      "Permissions",
      "Caching",
      "A bug",
      "Ansible keeps no state: it has no record it created the file, so add an explicit state: absent task or an allow-list purge"
    ],
    "correctIndex": 3,
    "explanation": "Terraform would destroy it; Ansible won't."
  },
  {
    "question": "Which command encrypts a secrets file, and what does the file start with?",
    "options": [
      "ansible-vault encrypt secrets.yml, starting $ANSIBLE_VAULT;1.1;AES256",
      "gpg -c, starting PGP",
      "openssl, starting BEGIN",
      "ansible-vault view"
    ],
    "correctIndex": 0,
    "explanation": "Encrypting twice gives different ciphertext."
  },
  {
    "question": "How do you restrict a run to one task group on one host?",
    "options": [
      "--tags <tag> with --limit <host> (tasks tagged always still run)",
      "--diff",
      "-f 1",
      "--check"
    ],
    "correctIndex": 0,
    "explanation": "Combine with --check to preview."
  },
  {
    "question": "A scheduled pipeline must show whether any host has drifted without changing anything. What do you run?",
    "options": [
      "The playbook for real",
      "ansible-lint",
      "The playbook with --check --diff, reporting changed tasks (exit non-zero on drift)",
      "--syntax-check"
    ],
    "correctIndex": 2,
    "explanation": "Check mode is the drift audit."
  },
  {
    "question": "A second CI run of a new playbook reports changed=1 because a task writes the current time into a file. What does the pipeline do?",
    "options": [
      "Pass",
      "Ignore it",
      "Skip it",
      "Fail the idempotence step, since the task would flap on every run in production"
    ],
    "correctIndex": 3,
    "explanation": "Idempotence is a CI gate."
  },
  {
    "question": "Which tool owns creating VMs and load balancers, and which owns OS config and deployment steps?",
    "options": [
      "Ansible for both",
      "Neither",
      "Terraform owns infrastructure; Ansible owns on-host config and orchestration",
      "Terraform for both"
    ],
    "correctIndex": 2,
    "explanation": "Pick one owner per resource."
  }
]
</script>

## Coding challenges

Try these on your own computer, then compare your output. Nothing you write is sent anywhere.

### Render a config template

Write the Jinja2 template that renders an nginx-style server block: a managed-by header, listen port, server_name (appending .example.com only when env is 'production') and one comment line per upstream with loop.index, name and weight defaulting to 1. Print the staging render, then the production server_name line. (Needs Jinja2: pip install jinja2.)

**Starter code**

```yaml
from jinja2 import Environment
env = Environment(trim_blocks=True, lstrip_blocks=True)
TEMPLATE = """# TODO: write the Jinja2 template: managed-by header, listen port,
# server_name (add .example.com when env == 'production'), and one comment per upstream
# with loop.index, name and weight (default 1)
"""
vars_ = {"http_port": 8081, "inventory_hostname": "web1", "env": "staging",
         "upstreams": [{"name": "a", "weight": 3}, {"name": "b"}]}
print(env.from_string(TEMPLATE).render(**vars_))
vars_["env"] = "production"
print(env.from_string(TEMPLATE).render(**vars_).splitlines()[3])
```

**Expected output**

```text
# managed by Ansible - do not edit by hand
server {
    listen 8081;
    server_name web1;
    # upstream 1: a weight=3
    # upstream 2: b weight=1
}
    server_name web1.example.com;
```

<details><summary>Show solution and explanation</summary>

<pre><code>from jinja2 import Environment
env = Environment(trim_blocks=True, lstrip_blocks=True)
TEMPLATE = &quot;&quot;&quot;# managed by Ansible - do not edit by hand
server {
    listen {{ http_port }};
    server_name {{ inventory_hostname }}{% if env == &#x27;production&#x27; %}.example.com{% endif %};
{% for u in upstreams %}
    # upstream {{ loop.index }}: {{ u.name }} weight={{ u.weight | default(1) }}
{% endfor %}
}
&quot;&quot;&quot;
vars_ = {&quot;http_port&quot;: 8081, &quot;inventory_hostname&quot;: &quot;web1&quot;, &quot;env&quot;: &quot;staging&quot;,
         &quot;upstreams&quot;: [{&quot;name&quot;: &quot;a&quot;, &quot;weight&quot;: 3}, {&quot;name&quot;: &quot;b&quot;}]}
print(env.from_string(TEMPLATE).render(**vars_))
vars_[&quot;env&quot;] = &quot;production&quot;
print(env.from_string(TEMPLATE).render(**vars_).splitlines()[3])
</code></pre>

<p>Ansible&#x27;s template module uses Jinja2, so {{ }} prints values, {% if %} and {% for %} control flow, and the default filter handles optional weights. Verified by running the solution with Jinja2.</p>
</details>

### A dynamic inventory

Write build(text) that turns the CMDB CSV into an Ansible dynamic-inventory structure: _meta hostvars (ansible_host and an integer http_port per host), and every host joins two groups, its role and its env. Print each group's hosts and one host's variables.

**Starter code**

```yaml
import csv, io, json

CSV = """name,address,role,env,port
web-01,10.0.1.11,web,prod,8080
web-02,10.0.1.12,web,prod,8080
db-01,10.0.2.21,db,prod,5432
web-stg,10.1.1.11,web,staging,8081
"""

def build(text):
    # return {"_meta": {"hostvars": {name: {ansible_host, http_port(int)}}}, "all": {...}, "<group>": {"hosts": [...]}}
    # every row joins two groups: its role and its env
    pass

inv = build(CSV)
for g in ("web", "prod", "db", "staging"):
    print(f"{g}: {', '.join(inv[g]['hosts'])}")
print(json.dumps(inv["_meta"]["hostvars"]["web-01"], sort_keys=True))
```

**Expected output**

```text
web: web-01, web-02, web-stg
prod: web-01, web-02, db-01
db: db-01
staging: web-stg
{"ansible_host": "10.0.1.11", "http_port": 8080}
```

<details><summary>Show solution and explanation</summary>

<pre><code>import csv, io, json

CSV = &quot;&quot;&quot;name,address,role,env,port
web-01,10.0.1.11,web,prod,8080
web-02,10.0.1.12,web,prod,8080
db-01,10.0.2.21,db,prod,5432
web-stg,10.1.1.11,web,staging,8081
&quot;&quot;&quot;

def build(text):
    inv = {&quot;_meta&quot;: {&quot;hostvars&quot;: {}}, &quot;all&quot;: {&quot;children&quot;: [&quot;ungrouped&quot;]}}
    for row in csv.DictReader(io.StringIO(text)):
        inv[&quot;_meta&quot;][&quot;hostvars&quot;][row[&quot;name&quot;]] = {&quot;ansible_host&quot;: row[&quot;address&quot;], &quot;http_port&quot;: int(row[&quot;port&quot;])}
        for g in (row[&quot;role&quot;], row[&quot;env&quot;]):
            inv.setdefault(g, {&quot;hosts&quot;: []})[&quot;hosts&quot;].append(row[&quot;name&quot;])
    return inv

inv = build(CSV)
for g in (&quot;web&quot;, &quot;prod&quot;, &quot;db&quot;, &quot;staging&quot;):
    print(f&quot;{g}: {&#x27;, &#x27;.join(inv[g][&#x27;hosts&#x27;])}&quot;)
print(json.dumps(inv[&quot;_meta&quot;][&quot;hostvars&quot;][&quot;web-01&quot;], sort_keys=True))
</code></pre>

<p>An inventory script prints JSON with _meta so Ansible needn&#x27;t call --host for every host. A source of truth like a CMDB avoids the rot of hand-edited files. Verified by running the solution.</p>
</details>
