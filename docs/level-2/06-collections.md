---
description: "Collections and Galaxy: what ansible-core ships, installing a collection, FQCN resolution, requirements.yml, pinning and missing-collection errors."
---

# 06 · Collections, Galaxy and Dependencies

`ansible-core` is deliberately small: it contains the engine and the `ansible.builtin` modules and plugins. Everything else (cloud providers, databases, network vendors, utilities) is distributed as **collections**, versioned packages of modules, plugins, roles and documentation. Managing collections is managing your automation's dependencies.

!!! note "What was run"
    On this install `ansible-galaxy collection list` found no collections (only the built-ins that live inside ansible-core). I installed `ansible.utils` 6.1.1 from Galaxy into a project directory with `ansible-galaxy collection install ansible.utils -p ./collections`, which took about 9 seconds, and used its filters and tests. The larger `ansible` community package (which bundles many collections) was **not** installed. Network access to Galaxy worked in this environment; yours may be proxied or offline.

## What is in ansible-core

`ansible-doc -l` listed **71** modules on this install: all `ansible.builtin` (`file`, `copy`, `template`, `command`, `debug`, `assert`, `uri`, `get_url`, `user`, `service` ...). Anything else needs a collection. The community-maintained `ansible` package is a convenience bundle that installs ansible-core plus many collections; production setups usually install only the collections they use, pinned.

## Naming: namespace.collection.plugin

A fully qualified collection name has three parts: `ansible.utils.ipaddr` is the filter `ipaddr` in the collection `utils` of the namespace `ansible`. Modules, filters, tests, lookups, callbacks and inventory plugins are all addressed this way. With FQCNs there is no ambiguity about which implementation runs, which matters because two collections can ship a module with the same short name.

Resolution failures give precise messages (all real):

```text
couldn't resolve module/action 'nosuch.collection.thing'. This often indicates a misspelling, missing collection, or incorrect module path.
No filter named 'ansible.utils.nonexistent'.
No test named 'ansible.utils.ip'.      # collection not installed (before I installed it)
```

An unknown **module/action** aborts the whole play at load time (`ignore_errors` does not help, because it is a parse-time error), while an unknown **filter or test** fails only when the task is templated, as an ordinary task failure.

## Where collections live

Ansible searches `collections_paths` (the `ANSIBLE_COLLECTIONS_PATH` environment variable or `ansible.cfg`), a list of directories each containing `ansible_collections/<namespace>/<name>/`. Installing with `-p ./collections` creates `./collections/ansible_collections/ansible/utils`. Per-project collection directories are good practice: the project carries its dependencies and does not depend on whatever happens to be installed in a user's home directory. With `ANSIBLE_COLLECTIONS_PATH=./collections` the earlier `collection list` showed:

```text
# .../collections/ansible_collections
Collection    Version
ansible.utils 6.1.1
```

## requirements.yml

Declare dependencies in a file and install them in one command:

```yaml
---
collections:
  - name: ansible.utils
    version: ">=6.0.0,<7.0.0"
  - name: community.general
    version: "11.0.0"
roles:
  - name: some.role
    version: v1.2.3
```

`ansible-galaxy collection install -r requirements.yml -p ./collections` installs them. Choices that matter:

- **Pin versions**, or at least a major range. An unpinned install gets whatever is latest, so a pipeline can break with no commit on your side. A fully reproducible setup pins exact versions and updates them deliberately (a bot or a scheduled task).
- **Pin ansible-core too** (in `requirements.txt` for pip): collections declare a minimum ansible-core version, and upgrades of core change behaviour (this course found `when:` with a string failing on 2.21.5).
- **Python dependencies** of plugins (`netaddr` for `ipaddr`, `jmespath` for `json_query`, cloud SDKs) are not installed by `ansible-galaxy`. Put them in `requirements.txt` (and in the execution environment, Level 4 · 01). I had to `pip install netaddr` before the IP filters worked.
- **Trust.** A collection is code that runs on your controller and, as modules, on your targets. Install from sources you trust, review release notes, and consider an internal Galaxy/Automation Hub mirror. A typosquatted collection name is a supply-chain risk (CI/CD course, Level 3 · 08).

## Roles from Galaxy and from Git

Roles can be installed with `ansible-galaxy role install -r requirements.yml` into `roles_path`, from Galaxy names or Git URLs (`src: https://...git`, `version: <tag or commit>`). Pin to a tag or commit SHA. Consider vendoring the role into your repository when it is small and you need to review every line.

## Building your own collection

When roles, modules and plugins are shared across projects, package them as a collection: `ansible-galaxy collection init mycompany.platform` creates the skeleton (`galaxy.yml`, `roles/`, `plugins/modules/`, `plugins/filter/`, `docs/`), `ansible-galaxy collection build` makes a tarball, and `install` accepts a path or a tarball. Use semantic versioning and a changelog, tested in CI, and publish to a private repository. Level 3 builds a custom module and a plugin; they can be dropped into such a collection unchanged.

## Using collections in playbooks

A play can set a search order with `collections:` (so you may write short names), but that reintroduces ambiguity; this course and `ansible-lint` prefer FQCNs everywhere. Lint flagged short names in the bad example in Lesson 09: `fqcn[action-core]: Use FQCN for builtin module actions (shell)`.

## Reproducibility checklist

1. `requirements.txt` with pinned `ansible-core` and Python libraries.
2. `requirements.yml` with pinned collections and roles.
3. A documented bootstrap command (or a container image, Level 4 · 01).
4. The same versions in CI as on workstations.
5. A scheduled job that tries the latest versions in a branch, so upgrades are discovered before they are forced.

## How It Actually Works

The plugin loader keeps a mapping from FQCN to files discovered by scanning each directory in `collections_paths` for `ansible_collections/<ns>/<name>/plugins/<type>/`. When a task names `ansible.utils.ipaddr`, the loader finds the collection, imports the plugin file, and caches the loaded plugin. Each collection can include a `meta/runtime.yml` with **redirects and deprecations** (a module renamed between collections keeps working through a redirect for a while, printing a deprecation warning), and `requires_ansible` to state compatible core versions. For module plugins, the controller packages the module file with Ansiballz, a self-extracting zip containing the module and its Python helpers from `ansible.module_utils`, and ships it to the target, which is why a collection's modules do not have to be pre-installed on the managed hosts.

## Common mistakes

- **Unpinned collections and core**, so builds change on their own.
- **Forgetting the Python dependency** of a filter or module.
- **Installing into the user's home** and relying on it silently.
- **Short module names** that resolve differently once a collection is added.
- **Treating a collection as trusted** because it is on Galaxy.
- **Not testing upgrades.**
- **A missing collection discovered mid-pipeline**, not at the start; install and `ansible-doc` check first.

## Exercise

1. Install `ansible.utils` into a project directory with `-p`, point `ANSIBLE_COLLECTIONS_PATH` at it, and run an `ipaddr` filter. Then unset the variable and read the error.
2. Write a `requirements.yml` for your project with pinned versions and a bootstrap script that installs it and checks `ansible-doc` for one module from each collection.
3. Create a collection skeleton with `ansible-galaxy collection init` and move one role into it. Run it with its FQCN.
4. Write the upgrade procedure for `ansible-core` in your environment: branch, install, run the test suite, compare lint output, roll forward.
