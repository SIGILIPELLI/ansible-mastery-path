---
description: "Targeting runs: tags, always and never, skip-tags, limit, check mode on subsets, and zero-host behaviour, each measured with real runs."
---

# 07 · Tags, Limits and Targeting

A playbook that configures a whole fleet is the wrong thing to run when you want to change one setting on one host. Ansible gives you three ways to narrow a run: **tags** (which tasks), **limits** (which hosts) and **check mode** (whether to change anything). Used well they make a large playbook safe to run; used carelessly they cause partial, inconsistent states.

!!! note "What was run"
    The tag and limit results below were produced by a real run of `src/l2/tags.yml` against two local hosts, and the exit-status checks come from the shell. Behaviour is for ansible-core 2.21.5.

## Tags: which tasks run

```yaml
tasks:
  - ansible.builtin.debug: {msg: "install"}
    tags: [install, setup]
  - ansible.builtin.debug: {msg: "configure"}
    tags: [configure, setup]
  - ansible.builtin.debug: {msg: "always runs"}
    tags: [always]
  - ansible.builtin.debug: {msg: "never unless asked"}
    tags: [never, debug_only]
  - ansible.builtin.debug: {msg: "untagged"}
```

Measured results (messages printed on host `w1`):

| Command | Tasks that ran |
|---|---|
| (no options) | install, configure, always runs, untagged |
| `--tags configure` | configure, **always runs** |
| `--skip-tags setup` | always runs, untagged |
| `--tags debug_only` | always runs, **never unless asked** |
| `--tags nonexistent` | always runs |
| `--tags setup --skip-tags configure` | install, always runs |

Rules shown by the table:

- **No options runs untagged and tagged tasks alike**, except tasks tagged `never`.
- **`--tags X` runs only tasks with tag X**, so **untagged tasks do not run**; this is a frequent surprise when you tag only some tasks.
- **`always`** tasks run regardless of `--tags` (not if you `--skip-tags always`). Use it for tasks other tasks depend on, such as loading variables or fact gathering helpers.
- **`never`** tasks are excluded unless you explicitly select another tag they carry. Good for destructive or diagnostic tasks.
- **`--skip-tags` wins** over `--tags` when both match the same task.
- A task selected by tag still has its `when:` evaluated.
- `--list-tags` shows the tag set: `[always, configure, debug_only, install, never, setup]`.

### Tag hygiene

Tags are easy to misuse. A tag selects a task but does not include its **dependencies**: `--tags configure` skips an earlier `install` task. If configure needs a variable set by an untagged task earlier, it will fail in an odd way. Keep tagged tasks independent, or tag the prerequisite `always`. For roles, tags set on the role entry apply to all of the role's tasks; `import_role` tags are inherited statically; `include_role` needs `apply: {tags: ...}`. Use a small, documented vocabulary (`packages`, `config`, `service`, `users`) rather than a tag per task.

Do not make tags a substitute for structure. A playbook that has to be run with the right tags to work is a playbook that should be split into several playbooks or roles.

## Limits: which hosts run

`--limit` narrows the hosts of every play to an intersection with the given pattern:

- `--limit w1` or `-l w1`: one host.
- `--limit 'web:!w2'`: pattern expression (Lesson 03).
- `--limit @hosts.txt`: hosts listed one per line in a file. Running with `--limit @lim.txt` (containing `w2`) executed on `w2` only: `ok: [w2]`.
- `--limit nope` (matches nothing): printed `Specified inventory, host pattern and/or --limit leaves us with no hosts to target.` and **exited with status 1**. This is different from a play whose `hosts:` matches nothing, which exits 0 (Level 1 · 03). A `--limit` that leaves nothing is treated as an error, which is the safer behaviour.

`--limit` with `serial` and `run_once` interacts: `run_once` runs on the first host of the *limited* set, so limiting can change which host performs the one-time action. Test that if you rely on it.

A very common operational workflow:

1. `ansible-playbook site.yml --limit canary --check --diff` to preview.
2. `ansible-playbook site.yml --limit canary` to apply to a canary host or group.
3. Verify (smoke tests, monitoring).
4. `ansible-playbook site.yml --limit 'prod:!canary'` for the rest, perhaps in batches with `serial` (Lesson 08).

## `--check`, `--diff`, `--step`, `--start-at-task`

Check mode (Level 1 · 05) combines with limits and tags for targeted previews: `--tags config --limit web --check --diff` answers "what would a config change do to the web hosts?" without touching anything. Be aware of the caveat from Level 1: tasks that depend on earlier tasks' real effects (a package install) can mislead a check run that skips them.

`--step` prompts before each task. `--start-at-task` resumes at a named task but skips the earlier ones, which broke the sandbox setup in Level 1 · 09.

## Variables that depend on the run

Magic variables expose the selection: `ansible_run_tags`, `ansible_skip_tags`, `ansible_limit`, `ansible_check_mode`, `ansible_play_hosts`, `ansible_play_batch`. You can make playbooks refuse to run unsafely:

```yaml
- ansible.builtin.assert:
    that: ansible_limit is defined
    fail_msg: "Refusing to run against production without --limit. Use --limit canary first."
  run_once: true
  when: "'production' in group_names"
```

Guard rails like this are cheap; the cost is a little friction. I checked the variables: with no options `ansible_limit` was **undefined** (so `is defined` works as a test), `ansible_run_tags` was `['all']`, `ansible_skip_tags` was `[]` and `ansible_check_mode` was `False`; with `--limit n2 --tags all --skip-tags x --check` they were `n2`, `['all']`, `['x']` and `True`. The `assert` guard itself was not run.

## Separate playbooks vs tags

A playbook per operation (`site.yml`, `deploy.yml`, `rotate-keys.yml`, `patch.yml`) is easier to understand and review than one giant playbook with twenty tags. Use tags for modest sub-selection inside a playbook. Build an index (a README or `Makefile` targets) of the commands people should run, so operators do not invent their own tag combinations.

## How It Actually Works

Tag selection is applied when the play's task list is compiled for execution: each task has a set of tags (its own plus those inherited from blocks, roles and play), and the engine keeps a task if the run's tag filter says so. `always` and `never` are special tags handled in that filter. Limits are applied earlier, when the play's host pattern is evaluated: the effective host list is the intersection of the pattern and the limit. If the intersection is empty and a limit was given, the CLI aborts with the error shown above; if the pattern alone matched nothing, the play is skipped. The restriction is applied on the controller, so tasks excluded by tags or limits never reach a target and no connection is made to hosts outside the limit (which is one reason limits are also a performance tool).

## Common mistakes

- **Expecting `--tags` to run untagged setup tasks.**
- **Tagged tasks with hidden dependencies** on untagged ones.
- **`--limit` forgotten**, so production is changed along with the intended host.
- **Different behaviour assumed** between an empty `hosts:` match and an empty `--limit`.
- **Tags that mean different things** in different roles.
- **Using tags where separate playbooks would be clearer.**
- **No guard rails** against running on production without limits.

## Exercise

1. Reproduce the table with your own playbook and add a `--tags` combination you have not seen; predict the result first.
2. Show that `--limit` with a typo exits non-zero and that a `hosts:` typo does not; add a CI pre-step that catches both.
3. Write a guard-rail assertion that fails when the play would touch more than five hosts without an explicit `-e confirm=yes`.
4. Convert a tag-heavy playbook into three smaller playbooks and a `Makefile` with the commands operators should run.
