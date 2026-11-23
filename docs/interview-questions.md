---
title: "Ansible Interview Questions and Answers (179 Questions)"
description: "179 Ansible interview questions with answers and explanations, from beginner to advanced, organised by level. Free, from the Ansible Mastery Path."
---

# Ansible Interview Questions and Answers

**179 questions** with the correct answer and a short explanation, organised from beginner (Level 1) to advanced (Level 4). Every question comes from a lesson in the free Ansible Mastery Path, so you can open the lesson to go deeper.

!!! tip "Practise, don't just read"
    Each lesson also ends with an interactive quiz, and the [final quiz](quiz.md) tests all four levels. Try to answer each question below before reading the answer.

## Level 1 · Ansible Foundations

### [01 · What Ansible Is and How It Works](level-1/01-what-ansible-is.md)

**Q1.** How does Ansible reach managed nodes?

**Answer:** Agentless: over SSH, copying a module, running it, collecting JSON and deleting it (no Ansible daemon)

Managed nodes need sshd and Python.

**Q2.** Is Ansible push or pull?

**Answer:** Push: the control node decides when to run and reaches out

Contrast with pull tools where agents fetch config.

**Q3.** What runs Ansible?

**Answer:** The control node (a laptop or CI runner) with inventory, playbook and roles

ansible-playbook is the only program.

**Q4.** What caveat applies to 'declarative' tasks?

**Answer:** Tasks say what should be true, but modules like command can't know state, so idempotency is on you

It's declarative-ish.

### [02 · Ad-Hoc Commands, Modules and `ansible-doc`](level-1/02-adhoc-and-docs.md)

**Q5.** What is an ad-hoc command?

**Answer:** One module run on one or many hosts, e.g. ansible web1 -i hosts.ini -m command -a "echo hello"

-m selects the module and -a its arguments.

**Q6.** Why did `echo hello` via the command module report CHANGED?

**Answer:** The command module can't know whether anything changed

Idempotency is on you with command/shell.

**Q7.** What should module names be written as?

**Answer:** Fully qualified collection names such as ansible.builtin.copy

FQCN avoids ambiguity.

**Q8.** Which tool documents a module?

**Answer:** ansible-doc

It shows parameters and examples offline.

### [03 · Inventory: Hosts, Groups and Variables](level-1/03-inventory.md)

**Q9.** What does inventory define?

**Answer:** What exists: hosts, groups and variables

INI is compact; YAML suits lists and dictionaries.

**Q10.** What does `[prod:children]` with web and db mean?

**Answer:** Group prod contains the groups web and db

ansible-inventory --graph confirms the tree.

**Q11.** How do you inspect how Ansible understood inventory?

**Answer:** ansible-inventory --graph and --host &lt;name&gt;

Inspect before you trust.

**Q12.** Group variable http_port=80 on [web] and host http_port=8081 on web1: what does web1 get?

**Answer:** 8081: host variables override group variables

The --host output showed 8081 for web1 and 80 for web2.

### [04 · Playbook Anatomy: Plays, Tasks and Modules](level-1/04-playbook-anatomy.md)

**Q13.** What is a playbook?

**Answer:** A YAML list of plays, each mapping hosts to a list of tasks

Tasks run in order on each host.

**Q14.** What does gather_facts do?

**Answer:** Runs setup to collect host facts before tasks

It can be disabled to save time.

**Q15.** Why give tasks names?

**Answer:** They appear in output and make runs readable

Unnamed tasks print module names only.

**Q16.** What's a common YAML pitfall?

**Answer:** Indentation and unquoted special values like colons or booleans

Quote values that YAML might misread.

### [05 · Idempotency, `changed` and Check Mode](level-1/05-idempotency.md)

**Q17.** What should the recap show on a repeat run of a converged playbook?

**Answer:** changed=0

The recap is the instrument for idempotency.

**Q18.** Why does an unguarded command task report changed every run?

**Answer:** command/shell can't know state

State-aware modules like file and copy report ok on the second run.

**Q19.** How does `creates:` help a command task?

**Answer:** If the file exists the command is skipped, making it idempotent

A condition makes the command safe to repeat.

**Q20.** What does `changed_when: false` mean on a read-only command?

**Answer:** Reading never changes anything, so never report changed

changed_when and failed_when interpret results.

### [06 · Variables and Facts](level-1/06-variables-facts.md)

**Q21.** What does `{{ missing | default('fallback') }}` do when undefined?

**Answer:** Gives 'fallback'; without default an undefined variable is an error

default makes optional values safe.

**Q22.** What beats every other variable source?

**Answer:** Extra vars (-e)

They override even set_fact.

**Q23.** What does set_fact do?

**Answer:** Creates or changes a variable for the rest of the play for that host, higher in precedence than play vars

Shown by the debug before and after.

**Q24.** Why quote a value starting with {{ in YAML?

**Answer:** Otherwise YAML misreads it

Strings with a leading {{ must be quoted.

### [07 · Conditionals, Loops and Registered Results](level-1/07-conditionals-loops.md)

**Q25.** How is a task skipped by `when` reported?

**Answer:** skipping, and not counted as changed

when takes a Jinja2 expression without {{ }}.

**Q26.** How is `when` evaluated on a looped task?

**Answer:** Per item

For example when: item.admin.

**Q27.** What does loop_control: {label: ...} do?

**Answer:** Shortens the output label per item

It prints item.name instead of the whole dict.

**Q28.** What does `ansible_facts.os_family == 'Debian'` target?

**Answer:** Debian-family hosts only

On macOS os_family was Darwin, so it skipped.

### [08 · Templates and Handlers](level-1/08-templates-handlers.md)

**Q29.** What is a template?

**Answer:** A Jinja2 file (.j2) rendered per host into a config file

{{ }} prints values; {% if %} and {% for %} control flow.

**Q30.** Why add a managed-by header?

**Answer:** So people know hand edits will be reverted

Also keep logic out of templates.

**Q31.** What does `validate:` on template or copy do?

**Answer:** Checks the file before it replaces the live one

For example validating a config with the service's own checker.

**Q32.** When do handlers fire?

**Answer:** Once, at the end of the play, only if a notifying task changed

flush_handlers forces them earlier.

### [09 · Debugging and Reading Failures](level-1/09-debugging-playbooks.md)

**Q33.** How should you read an Ansible failure?

**Answer:** Top-down: the task, host, module, then what/why/where (file:line:column)

The origin shows the failing line.

**Q34.** What does `'x' is undefined` usually mean, and a first step?

**Answer:** Missing variable, typo, scope or ungathered fact; use debug: var=x

Check inventory and precedence.

**Q35.** What does UNREACHABLE point at?

**Answer:** The connection: SSH, host key, network or interpreter; use -vvv and try ssh by hand

FAILED with rc means the command ran and failed.

**Q36.** How do you inspect a module's arguments?

**Answer:** ansible-doc -s &lt;module&gt;

For 'Unsupported parameters' errors.

### [10 · Project — A Verified Baseline Playbook](level-1/10-project-baseline-playbook.md)

**Q37.** Why was the first run ok=6 and the second ok=5 changed=0?

**Answer:** The handler ran once on the first run; the second run changed nothing so no handler fired

Convergence: zero changes on repeat.

**Q38.** What does blockinfile manage?

**Answer:** A block of lines between marker comments, e.g. two sysctl settings

lineinfile edits a single line like PermitRootLogin.

**Q39.** What did the drift test show?

**Answer:** Hand edits (a bad line, a changed mode) were detected and corrected by re-running the playbook

The tests call the real ansible-playbook.

**Q40.** How were the 'servers' simulated?

**Answer:** Local directories (node1, node2) with the local connection, so it ran on a laptop

Tests verified results with pytest.

## Level 2 · Structure and Safety

### [01 · Roles: Reusable Structure](level-2/01-roles.md)

**Q41.** What does a role package?

**Answer:** Everything to configure one thing: tasks, default variables, templates, files, handlers

ansible-galaxy role init scaffolds the layout.

**Q42.** Defaults versus vars in a role?

**Answer:** defaults/main.yml holds variables users are meant to override (lowest precedence); vars/main.yml holds internal constants (high precedence)

defaults are the role's public interface.

**Q43.** Which file is the role's entry point?

**Answer:** tasks/main.yml

meta/main.yml holds author, platforms and dependencies.

**Q44.** Why validate inputs with assert at the start of the role?

**Answer:** Fail early with a clear message (e.g. port 1–65535) instead of failing deep inside later tasks

fail_msg explains the expected range.

### [02 · Variable Precedence, Measured](level-2/02-variable-precedence.md)

**Q45.** Which source wins above all others?

**Answer:** -e extra vars

They beat even set_fact.

**Q46.** Which source has the lowest precedence?

**Answer:** Role defaults/main.yml

That's why defaults are safe to override.

**Q47.** Host versus group variables?

**Answer:** Host beats group, and a specific group beats all

At both inventory levels.

**Q48.** How was the order established?

**Answer:** By measurement: a script generated a fresh project per trial, ran the playbook and read which source's value won

14 sources ranked by experiment.

### [03 · Jinja2 Filters and Expressions](level-2/03-jinja-filters.md)

**Q49.** What does `servers | selectattr('port','gt',100) | map(attribute='name') | list` return for ports 80, 8080, 443?

**Answer:** [b, c]

Ports above 100: b and c.

**Q50.** Why end with `| list` after map or selectattr?

**Answer:** They return generators; list (or join) materialises the result

Otherwise you print a generator object.

**Q51.** Shallow versus recursive combine of {a:1,b:{c:2,d:3}} with {b:{c:9},e:5}?

**Answer:** Shallow replaces b entirely ({c:9}); recursive=True merges ({c:9, d:3})

Variables from different layers don't merge on their own.

**Q52.** What does `'web-01.example.com' | regex_replace('^(\w+)-(\d+).*', '\2:\1')` give?

**Answer:** 01:web

Groups swapped; mind the backslashes in YAML.

### [04 · Blocks, Errors and Rescue](level-2/04-blocks-errors.md)

**Q53.** What happens by default when a task fails on a host?

**Answer:** Ansible stops that host's remaining tasks and continues with other hosts

Blocks, rescue and always change that.

**Q54.** What do block, rescue and always do?

**Answer:** block groups tasks; on failure the rest are skipped and rescue runs; always runs regardless

In the example 'never reached' was skipped.

**Q55.** Is rescue an automatic rollback?

**Answer:** No: it runs the tasks you wrote, which must themselves be idempotent and safe

A failing rescue task fails the host, but always still runs.

**Q56.** What does ansible_failed_task give inside rescue?

**Answer:** Details of the failed task (name, result)

Use it for a precise rollback message.

### [05 · Ansible Vault and Secrets](level-2/05-vault.md)

**Q57.** What does an encrypted vault file start with?

**Answer:** $ANSIBLE_VAULT;1.1;AES256 followed by hex ciphertext

Encrypted with ansible-vault encrypt.

**Q58.** Does encrypting the same content twice give the same ciphertext?

**Answer:** No: ciphertext differs each time

Random salt is used.

**Q59.** What happens with a wrong vault password?

**Answer:** Decryption failed (no vault secrets were found that could decrypt)

No secret supplied gives a different error.

**Q60.** What does ansible-vault rekey do?

**Answer:** Changes the password without changing the contents

Use --vault-password-file.

### [06 · Collections, Galaxy and Dependencies](level-2/06-collections.md)

**Q61.** What does ansible-core contain?

**Answer:** The engine and ansible.builtin modules and plugins; everything else lives in collections

71 builtin modules on the lesson's install.

**Q62.** What are the parts of a fully qualified collection name?

**Answer:** namespace.collection.plugin, e.g. ansible.utils.ipaddr

Install collections via ansible-galaxy.

**Q63.** What happens with an unknown module/action?

**Answer:** The whole play aborts at load time; ignore_errors doesn't help

Resolution errors are precise.

**Q64.** How do you pin collection versions for a project?

**Answer:** A requirements.yml file installed with ansible-galaxy

Dependencies should be reproducible.

### [07 · Tags, Limits and Targeting](level-2/07-tags-limits.md)

**Q65.** What does `--tags configure` run?

**Answer:** configure tasks plus tasks tagged always

always runs unless skipped.

**Q66.** What does a task tagged `never` do with no options?

**Answer:** It doesn't run unless asked via its other tag

--tags debug_only runs it.

**Q67.** Which tasks run with no options?

**Answer:** Untagged and tagged tasks alike, except those tagged never

install, configure, always and untagged ran.

**Q68.** What does --limit do?

**Answer:** Restricts which hosts the play targets

Combine with tags and check mode to target one change on one host.

### [08 · Delegation, Serial Batches and Strategies](level-2/08-delegation-strategies.md)

**Q69.** What does delegate_to do?

**Answer:** Runs the task on another host while keeping the original host's variable context

For example draining a host from a load balancer via lb1.

**Q70.** What's a delegation gotcha?

**Answer:** Parallel delegated tasks against one host can race; facts attach to the delegated host only with delegate_facts

command isn't a shell, so $(...) printed literally.

**Q71.** What does run_once do?

**Answer:** Runs a task on one host in the batch instead of every host

Useful for migrations.

**Q72.** Why use serial batches?

**Answer:** Roll changes through hosts in small groups, with max_fail_percentage to stop on problems

They limit blast radius.

### [09 · Testing and Linting Ansible](level-2/09-testing-ansible.md)

**Q73.** What does ansible-playbook --syntax-check do?

**Answer:** Parses the playbook without connecting, catching YAML and structural errors

The first rung of the testing ladder.

**Q74.** What does ansible-lint's `no-changed-when` flag?

**Answer:** command/shell without changed_when, which breaks idempotency reporting

Others: fqcn, name, no-free-form, package-latest.

**Q75.** Why does `state: latest` get flagged?

**Answer:** It makes runs non-reproducible

Pin versions or use present.

**Q76.** What are lint profiles?

**Answer:** Rule sets from basic to production that a playbook can meet

The fixed playbook passed 'production'.

### [10 · Project — A Tested Role](level-2/10-project-tested-role.md)

**Q77.** What does the webapp role's interface consist of?

**Answer:** defaults/main.yml variables (port, workers, root), with internal constants in vars/main.yml, documented in a README

The role has validation and a handler.

**Q78.** What does the 'idempotent' test assert?

**Answer:** A second run exits 0 and changed=0 for every host

Using real ansible-playbook runs.

**Q79.** What does the 'invalid port fails before changing anything' test show?

**Answer:** Validation with assert stops early with a non-zero exit and a clear message

webapp_port=70000 is rejected.

**Q80.** What does the check-mode test assert?

**Answer:** --check exits 0 and writes nothing (the output directory isn't created)

Nine tests all passed.

## Level 3 · Extending Ansible

### [01 · Writing a Custom Module](level-3/01-custom-modules.md)

**Q81.** When should you write a custom module?

**Answer:** When no module does what you need and command would be fragile

A module is a Python program.

**Q82.** How does a module report results?

**Answer:** exit_json on success and fail_json on failure

Plus an argument spec, check mode and diff support.

**Q83.** Why support check mode in a module?

**Answer:** So --check reports what would change without changing it

Be honest about 'changed'.

**Q84.** What's the argument spec?

**Answer:** A declaration of parameters, types, defaults and required fields that Ansible validates

It makes invalid input fail clearly.

### [02 · Filter and Lookup Plugins](level-3/02-filter-plugins.md)

**Q85.** What is a filter plugin?

**Answer:** A Python file with a FilterModule class whose filters() returns a dict of names to functions

Placed in filter_plugins/ next to the playbook or inside a role/collection.

**Q86.** Which design points matter?

**Answer:** Pure functions, native return types, validated inputs raising AnsibleFilterError, no mutation of arguments, documentation

mask_secrets returns a copy.

**Q87.** What do lookups do versus filters?

**Answer:** Lookups fetch data from outside the play (file, environment); filters transform data inside expressions

The lesson wrote an envfile lookup.

**Q88.** What does the mask_secrets filter mask?

**Answer:** Values whose keys look sensitive (password, secret, token)

Including nested dictionaries.

### [03 · Dynamic Inventory](level-3/03-dynamic-inventory.md)

**Q89.** Why do static inventories rot?

**Answer:** Servers are created and destroyed by autoscalers faster than a hand-edited file can track

Use a source of truth like a CMDB.

**Q90.** What must an inventory script print for --list?

**Answer:** Valid JSON including _meta hostvars, exit code 0; it also answers --host NAME

_meta avoids one call per host.

**Q91.** In the CSV example, which groups does web-01 belong to?

**Answer:** web (its role) and prod (its env)

Each row becomes a host in two groups.

**Q92.** What are the two ways shown to build dynamic inventory?

**Answer:** An inventory script and an inventory plugin

Plugins can also cache results.

### [04 · `command` and `shell` Without Breaking Idempotency](level-3/04-command-shell-pitfalls.md)

**Q93.** What can `command` NOT do?

**Answer:** Pipes, redirection, &amp;&amp;, $(...) and globbing, since there's no shell

shell runs through /bin/sh.

**Q94.** What is the safest form of command?

**Answer:** argv: a list where each element is one argument with no shell or splitting

`argv: [echo, "a b", "c;d"]` printed a b c;d.

**Q95.** How do you prevent injection through variables in shell?

**Answer:** The quote filter: `echo {{ evil | quote }}` treats it as data

Without it `ok; echo INJECTED` ran a second command.

**Q96.** What are raw and script for?

**Answer:** raw sends text over SSH without Python (bootstrapping); script copies and runs a local script

Last-resort tools.

### [05 · Async Tasks and Polling](level-3/05-async-polling.md)

**Q97.** Why use async?

**Answer:** A long task shouldn't hold the connection open for its entire life (large downloads, long jobs)

The task is started and checked later.

**Q98.** What does `poll: 0` mean?

**Answer:** Fire and forget: don't wait for the job

Check later with async_status.

**Q99.** What does async_status do?

**Answer:** Checks a started job's status, typically with retries until finished

Use `until` with retries and delay.

**Q100.** What does `async:` set?

**Answer:** The maximum time the job may run

poll sets how often Ansible checks.

### [06 · Performance: Forks, Pipelining and Facts](level-3/06-performance.md)

**Q101.** What does `forks` control, and what's the default?

**Answer:** Parallel worker processes handling hosts; default 5

Measured: 1 fork 50.1 s, 5 forks 11.1 s, 10 forks 6.6 s, 20 forks 4.5 s on 20 hosts.

**Q102.** When do more forks stop helping?

**Answer:** When forks reaches the host count; each fork is also a Python process using memory

Scaling is near linear until then.

**Q103.** What is gather_facts' hidden cost?

**Answer:** It runs the setup module on every host at the start of each play (about 2.3 s vs 0.4 s without, on 20 hosts)

Turn it off or use gather_subset or fact caching.

**Q104.** What does the free strategy help with?

**Answer:** Slow hosts holding others up at each task under linear

Under linear a slow host delays everyone per task.

### [07 · Rolling Updates and Failure Budgets](level-3/07-rolling-updates.md)

**Q105.** What does `serial: [1, "50%", "100%"]` give on eight hosts?

**Answer:** Batches of 1, 4 and 3: a canary, then half, then the rest

The first is the canary.

**Q106.** What's the principle 'drain first, re-enable last'?

**Answer:** Remove the host from rotation before changing it, and return it only after it passes the smoke test (always section)

Capacity stays up.

**Q107.** What does 'roll back locally, then fail loudly' mean?

**Answer:** The rescue restores the previous version on that host, logs it, then fails the host so the batch is marked failed

any_errors_fatal stops the rollout.

**Q108.** What's a failure budget?

**Answer:** How many failures a rollout tolerates (e.g. max_fail_percentage) before stopping

A bad change is stopped early.

### [08 · State, Drift and Convergence](level-3/08-state-and-drift.md)

**Q109.** Why does removing a task leave legacy.conf on the host?

**Answer:** Ansible keeps no state: it has no record that it created the file

Terraform would remove it; Ansible does nothing.

**Q110.** What is Fix 1 for orphans?

**Answer:** An explicit removal task (state: absent), kept until every environment has run it

Track it in a changelog.

**Q111.** What is Fix 2?

**Answer:** An allow-list purge: find files in a directory and delete everything not in the managed list

In --check it showed what would be deleted without deleting.

**Q112.** What can happen when two tasks fight each other?

**Answer:** They keep undoing each other's change every run, so changed never reaches zero

The flip.yml experiment.

### [09 · Network and Windows Targets](level-3/09-network-windows.md)

**Q113.** What protocols manage Windows hosts?

**Answer:** WinRM or PSRP (the control node must be Linux or macOS)

ansible.windows ships 81 modules in the lesson's version.

**Q114.** How honest is the lesson about verification?

**Answer:** No Windows host, network device or API was available, so nothing was executed against them; it's based on documentation and ansible-doc

It says so up front.

**Q115.** What connection type do network devices use?

**Answer:** network_cli (and related connections from ansible.netcommon)

The device has no Python to run modules on.

**Q116.** For non-Windows targets, which module should you use instead of win_copy?

**Answer:** ansible.builtin.copy

As the module doc states.

### [10 · Project — A Tested Custom Module](level-3/10-project-custom-module.md)

**Q117.** What does the kvfile module manage?

**Answer:** key=value entries: state present ensures one line for the key; absent removes it

It preserves comments and unrelated settings.

**Q118.** Why a pure apply(lines, key, value, state) function?

**Answer:** Only it decides what changes, making it easy to test; main() wires AnsibleModule and file operations

25 tests cover it.

**Q119.** What do check and diff mode do in kvfile?

**Answer:** Check never writes; diff returns before and after content

Atomic writes avoid half-written files.

**Q120.** Which sequence of changed flags did the playbook show: set, set again, change to 8, remove?

**Answer:** [True, False, True, True]

The second set was idempotent.

## Level 4 · Operating Ansible

### [01 · Controllers, AWX and Execution Environments](level-4/01-automation-platform.md)

**Q121.** What does a controller (AWX/AAP) add beyond ansible-playbook?

**Answer:** Projects, inventories, credentials, job templates, RBAC, scheduling, workflows, history/logging, API, and execution isolation

For teams: who may run what against which hosts.

**Q122.** What is the most valuable credential feature?

**Answer:** Separation: an operator can use a credential to launch a job without ever seeing its secret

Credentials are encrypted stores.

**Q123.** How do AWX and AAP relate?

**Answer:** AWX is the upstream open-source project; AAP is Red Hat's commercial product built on it

The lesson notes nothing was installed or run.

**Q124.** What do execution environments provide?

**Answer:** Jobs run in separate containers rather than on a shared shell

Built with ansible-builder.

### [02 · Ansible in CI/CD](level-4/02-ansible-in-ci.md)

**Q125.** Why order the pipeline 'cheapest check first'?

**Answer:** Run the fastest, most likely-to-fail checks first to fail early

syntax-check, lint, secret hygiene, converge, idempotence, check mode.

**Q126.** What does the idempotence step catch?

**Answer:** A non-idempotent task: the second run must report changed=0

The nanosecond-writing task made changed=1 each run and failed the step.

**Q127.** What does the check-mode step verify?

**Answer:** --check reports changed=0, meaning no drift

The last rung.

**Q128.** What does the secret hygiene step check?

**Answer:** Tasks using secret variables have no_log

A custom linter (nologlint.py).

### [03 · Secrets and Credentials at Scale](level-4/03-secrets-at-scale.md)

**Q129.** Why use an executable vault password script in CI?

**Answer:** A file is awkward; the script reads an environment variable and prints the password, failing closed if it's missing

Missing variable: the script exits 1 and Ansible errors.

**Q130.** What does 'fails closed' mean here?

**Answer:** A missing secret stops the run rather than proceeding unprotected

The error was 'Vault password script returned non-zero'.

**Q131.** How do you keep separate secrets per environment?

**Answer:** Multiple vault IDs: --vault-id dev@dev_pass.py --vault-id prod@prod_pass.py

A single repository can hold both.

**Q132.** What does no_log protect?

**Answer:** Secrets appearing in task output and logs at run time

Vault protects at rest; no_log protects output.

### [04 · Pull Mode and Bootstrap](level-4/04-pull-mode.md)

**Q133.** What does ansible-pull do?

**Answer:** The host pulls its own configuration from Git and runs it locally

It's the opposite of push.

**Q134.** What does 'only if changed' mean?

**Answer:** It runs the playbook only when the repository has new commits (unless forced)

Saves work on unchanged repos.

**Q135.** Which hosts suit pull mode?

**Answer:** Many hosts that can't be reached from a controller, or that bootstrap themselves

It scales without a push controller.

**Q136.** How does pull mode repair drift?

**Answer:** By re-running periodically (e.g. cron), reapplying the desired state

The lesson showed drift repair.

### [05 · Terraform and Ansible Together](level-4/05-terraform-and-ansible.md)

**Q137.** What is the division of labour?

**Answer:** Terraform for networks, VMs, load balancers, databases, DNS; Ansible for OS packages, config, users, services and deployment steps

Neither tool is a secret store.

**Q138.** What if both tools create the same cloud resources?

**Answer:** They'll fight: pick one owner per resource

The overlap is a trap.

**Q139.** Name a handoff pattern.

**Answer:** terraform output -json feeding an inventory, or an Ansible cloud inventory plugin (aws_ec2, azure_rm) querying tagged instances

A community plugin can also read state.

**Q140.** How honest is the lesson?

**Answer:** Terraform wasn't installed, so no apply ran; the handoff logic was built and tested without state

It states what wasn't run.

### [06 · Auditing Drift with Check Mode](level-4/06-drift-audit.md)

**Q141.** Why not parse console output for drift?

**Answer:** It's for humans, mixing headers, items, diffs and warnings; use a callback plugin that writes JSON

The driftreport plugin records changed results.

**Q142.** How does the runner audit drift?

**Answer:** Runs the playbook with --check --diff and the plugin enabled, then reports with exit codes

Exit 0 means no drift.

**Q143.** What must you set to enable the callback plugin?

**Answer:** ANSIBLE_CALLBACKS_ENABLED=driftreport and ANSIBLE_CALLBACK_PLUGINS=&lt;dir&gt;

The aggregate plugin needs enabling.

**Q144.** What is drift?

**Answer:** The difference between what automation says and what a machine actually has

Check mode reveals it without changing anything.

### [07 · Automation Incidents and Blast Radius](level-4/07-incidents.md)

**Q145.** Why does automation 'multiply mistakes as well as effort'?

**Answer:** One wrong hosts: pattern or bad variable changes every targeted host at once

Control blast radius.

**Q146.** Which control addresses 'wrong target'?

**Answer:** A preflight guard, protected groups and limits

The tested preflight.py computes the blast radius first.

**Q147.** Which control addresses 'batch too large'?

**Answer:** serial, failure budget and tested abort semantics

200 hosts restarted at once is the example.

**Q148.** How can a scheduled drift repair cause an incident?

**Answer:** It reverts an emergency hot patch; audit drift before applying

Review drift first.

### [08 · Migrating Scripts and Avoiding Anti-Patterns](level-4/08-migration-antipatterns.md)

**Q149.** Why isn't the provisioning script idempotent?

**Answer:** mkdir fails if the directory exists (set -e exits 1), and &gt;&gt; appends port=8080 again on re-run

It's correct only from one starting state and only once.

**Q150.** What does the playbook equivalent give?

**Answer:** State-aware modules that converge: reruns change nothing

Compare repeated runs.

**Q151.** What happened without set -e after two runs?

**Answer:** app.conf contained port=8080 twice

The script 'worked' silently wrong.

**Q152.** What's the migration lesson?

**Answer:** Don't just wrap scripts in shell tasks: use modules and desired state, or idempotency is still on you

Avoid anti-patterns.

### [09 · Governance, Review and Standards](level-4/09-governance.md)

**Q153.** Why write standards down and enforce them with tools?

**Answer:** With ten authors quality drifts; a rule with an automated check is enforced, one nobody can check is ignored

Keep rules few and checkable.

**Q154.** Which standards belong in the one-pager?

**Answer:** Layout, naming, modules (FQCN), variables, safety (no_log, assert, serial), testing, pinned versions, documentation, release tagging

Nine areas.

**Q155.** What are ansible-lint profiles?

**Answer:** Rule sets of increasing strictness (min, basic, moderate, safety, shared, production)

Choose by risk.

**Q156.** What do warn_list and skip_list do?

**Answer:** warn_list reports without failing the build; skip_list isn't checked at all

A ratchet tightens over time.

### [10 · Capstone — Managing a Simulated Fleet](level-4/10-capstone-fleet.md)

**Q157.** What does the capstone fleet consist of?

**Answer:** A simulated 12-node fleet (web01–08, db01–04) with generated inventory and local connections

No remote hosts, SSH or privilege escalation were involved.

**Q158.** What did the idempotence step assert?

**Answer:** Second run changed=0 on all 12 nodes

After the first converge of changed=6 on every node.

**Q159.** What did the preflight step refuse?

**Answer:** `all` (exceeds --max-hosts 5) and a single production node without confirmation

Blast-radius control.

**Q160.** What did the targeted repair do?

**Answer:** With --limit web03,db02,web07 only those three hosts ran and changed, leaving the rest untouched

Then a clean audit exited 0.

## Mixed questions across all levels

**Q161.** A playbook reports `changed=1` on every run for this task. Why?

```yaml
- ansible.builtin.command: echo hi
```

**Answer:** command can't know state, so it reports changed every time; add changed_when: false (read-only) or creates:/guards

State-aware modules like file and copy report ok on repeat runs.

**Q162.** Which task is idempotent?

**Answer:** ansible.builtin.file: {path: /etc/app, state: directory, mode: '0755'}

mkdir fails when it exists, and &gt;&gt; appends duplicates.

**Q163.** On a repeat run of a converged playbook, what should the recap show?

**Answer:** changed=0

The recap is the instrument.

**Q164.** `http_port` is 80 in [web:vars], 8081 on host web1, and web1 runs with `-e http_port=9000`. Which wins for web1?

**Answer:** 9000: extra vars beat everything

Host beats group and extra vars beat both (measured precedence).

**Q165.** A role's defaults/main.yml sets webapp_port: 8080 and a play passes webapp_port: 9000 as a role parameter. What happens?

**Answer:** The role parameter overrides the default, since defaults have the lowest precedence

defaults are the role's public interface.

**Q166.** `servers | selectattr('port','gt',100) | map(attribute='name') | list` with ports 80, 8080, 443 (names a, b, c) returns:

**Answer:** [b, c]

Ports above 100: 8080 and 443.

**Q167.** Shallow versus recursive combine of {a:1, b:{c:2, d:3}} with {b:{c:9}, e:5}.

**Answer:** Shallow: {a:1, b:{c:9}, e:5}; recursive=True: {a:1, b:{c:9, d:3}, e:5}

A plain combine replaces whole values for matching keys.

**Q168.** A handler is notified by three tasks that each changed. How often does it run?

**Answer:** Once, at the end of the play

Handlers fire once per play unless flushed.

**Q169.** A task with `when: ansible_facts.os_family == 'Debian'` runs on macOS. What's reported?

**Answer:** skipping: not counted as changed (os_family is Darwin)

Skipped tasks aren't changed.

**Q170.** Which structure runs a health check and rolls back on failure but always cleans up?

**Answer:** block with rescue (rollback) and always (cleanup)

Rescue runs only when the block fails; always runs regardless.

**Q171.** What does `serial: [1, "50%", "100%"]` produce on eight hosts?

**Answer:** Batches of 1, 4 and 3: a canary, then half, then the rest

Verified by arithmetic: 1, then 50% of 8 = 4, then the remaining 3.

**Q172.** An 'UNREACHABLE' error indicates what, and what's the first step?

**Answer:** A connection problem (SSH, host key, network or interpreter); use -vvv and try ssh by hand

FAILED with rc= means the command ran and failed.

**Q173.** `command: echo {{ user_input }}` is run with user_input 'ok; rm -rf x' under shell. How do you make it safe?

**Answer:** Use `{{ user_input | quote }}` (or avoid shell and pass argv)

The variable text is pasted into the shell line.

**Q174.** A task removed from the playbook leaves its file on every host. Why?

**Answer:** Ansible keeps no state: it has no record it created the file, so add an explicit state: absent task or an allow-list purge

Terraform would destroy it; Ansible won't.

**Q175.** Which command encrypts a secrets file, and what does the file start with?

**Answer:** ansible-vault encrypt secrets.yml, starting $ANSIBLE_VAULT;1.1;AES256

Encrypting twice gives different ciphertext.

**Q176.** How do you restrict a run to one task group on one host?

**Answer:** --tags &lt;tag&gt; with --limit &lt;host&gt; (tasks tagged always still run)

Combine with --check to preview.

**Q177.** A scheduled pipeline must show whether any host has drifted without changing anything. What do you run?

**Answer:** The playbook with --check --diff, reporting changed tasks (exit non-zero on drift)

Check mode is the drift audit.

**Q178.** A second CI run of a new playbook reports changed=1 because a task writes the current time into a file. What does the pipeline do?

**Answer:** Fail the idempotence step, since the task would flap on every run in production

Idempotence is a CI gate.

**Q179.** Which tool owns creating VMs and load balancers, and which owns OS config and deployment steps?

**Answer:** Terraform owns infrastructure; Ansible owns on-host config and orchestration

Pick one owner per resource.

## Practical coding questions

### Render a config template

Write the Jinja2 template that renders an nginx-style server block: a managed-by header, listen port, server_name (appending .example.com only when env is 'production') and one comment line per upstream with loop.index, name and weight defaulting to 1. Print the staging render, then the production server_name line. (Needs Jinja2: pip install jinja2.)

Starter code:

```
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

Expected output:

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

??? success "Show a solution"

    ```
    from jinja2 import Environment
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    TEMPLATE = """# managed by Ansible - do not edit by hand
    server {
        listen {{ http_port }};
        server_name {{ inventory_hostname }}{% if env == 'production' %}.example.com{% endif %};
    {% for u in upstreams %}
        # upstream {{ loop.index }}: {{ u.name }} weight={{ u.weight | default(1) }}
    {% endfor %}
    }
    """
    vars_ = {"http_port": 8081, "inventory_hostname": "web1", "env": "staging",
             "upstreams": [{"name": "a", "weight": 3}, {"name": "b"}]}
    print(env.from_string(TEMPLATE).render(**vars_))
    vars_["env"] = "production"
    print(env.from_string(TEMPLATE).render(**vars_).splitlines()[3])
    ```

    Ansible's template module uses Jinja2, so {{ }} prints values, {% if %} and {% for %} control flow, and the default filter handles optional weights. Verified by running the solution with Jinja2.

### A dynamic inventory

Write build(text) that turns the CMDB CSV into an Ansible dynamic-inventory structure: _meta hostvars (ansible_host and an integer http_port per host), and every host joins two groups, its role and its env. Print each group's hosts and one host's variables.

Starter code:

```
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

Expected output:

```text
web: web-01, web-02, web-stg
prod: web-01, web-02, db-01
db: db-01
staging: web-stg
{"ansible_host": "10.0.1.11", "http_port": 8080}
```

??? success "Show a solution"

    ```
    import csv, io, json

    CSV = """name,address,role,env,port
    web-01,10.0.1.11,web,prod,8080
    web-02,10.0.1.12,web,prod,8080
    db-01,10.0.2.21,db,prod,5432
    web-stg,10.1.1.11,web,staging,8081
    """

    def build(text):
        inv = {"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}}
        for row in csv.DictReader(io.StringIO(text)):
            inv["_meta"]["hostvars"][row["name"]] = {"ansible_host": row["address"], "http_port": int(row["port"])}
            for g in (row["role"], row["env"]):
                inv.setdefault(g, {"hosts": []})["hosts"].append(row["name"])
        return inv

    inv = build(CSV)
    for g in ("web", "prod", "db", "staging"):
        print(f"{g}: {', '.join(inv[g]['hosts'])}")
    print(json.dumps(inv["_meta"]["hostvars"]["web-01"], sort_keys=True))
    ```

    An inventory script prints JSON with _meta so Ansible needn't call --host for every host. A source of truth like a CMDB avoids the rot of hand-edited files. Verified by running the solution.

---

More free practice: the [Ansible Mastery Path](index.md) curriculum, the [Interview Prep Pack](https://learnmasterypath.com/interview-pack/) and the [free resume ATS check](https://learnmasterypath.com/resume/).
