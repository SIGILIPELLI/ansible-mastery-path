---
description: "Dynamic inventory: the script protocol, inventory plugins, hostvars and groups from a CSV, caching, and tests proving script and plugin match."
---

# 03 · Dynamic Inventory

Static inventories rot: servers are created and destroyed by autoscalers, and a hand-edited file can never keep up. A dynamic inventory asks an authoritative source (a cloud API, a CMDB, a database, Terraform state) for the hosts every time, so the inventory is always current.

!!! note "What was run"
    The authoritative source here is a small CSV file (`cmdb.csv`, four hosts). I built the inventory both as an **executable script** and as a **custom inventory plugin**, ran them through `ansible-inventory`, and wrote tests (including one proving the two produce the same data). Real cloud inventory plugins (AWS, Azure, GCP, VMware) were **not** run (no accounts); their usage is described from the documentation.

## The source data

```text
name,address,role,env,port
web-01,10.0.1.11,web,prod,8080
web-02,10.0.1.12,web,prod,8080
db-01,10.0.2.21,db,prod,5432
web-stg,10.1.1.11,web,staging,8081
```

Each row should become a host with variables (`ansible_host`, `http_port`) and membership of two groups, `role` and `env`.

## Option 1: an inventory script

Any executable that prints JSON in the right shape to `--list` (and answers `--host NAME`) can be used with `-i ./script`. The JSON format: group names map to `{hosts, vars, children}`, and a special `_meta.hostvars` key supplies **all host variables in one call** so Ansible does not run the script once per host.

```python
def build(path):
    inv = {"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}}
    for row in csv.DictReader(open(path)):
        inv["_meta"]["hostvars"][row["name"]] = {"ansible_host": row["address"], "http_port": int(row["port"]), "ansible_connection": "local"}
        for g in (row["role"], row["env"]):
            inv.setdefault(g, {"hosts": []})["hosts"].append(row["name"])
    return inv
```

Real output of `ansible-inventory -i ./inventory_script.py --graph`:

```text
@all:
  |--@ungrouped:
  |--@web:   web-01, web-02, web-stg
  |--@prod:  web-01, web-02, db-01
  |--@db:    db-01
  |--@staging: web-stg
```

and `--host web-01` returned `{"ansible_connection": "local", "ansible_host": "10.0.1.11", "http_port": 8080}`. A pattern `'web:&prod'` listed `web-01` and `web-02`, so groups from the script work in patterns like any others.

Script rules (all tested): `--list` exit code 0 and valid JSON with `_meta`; `--host` prints a JSON object (here `{}`, because `_meta` already supplied everything); an unknown flag prints usage to stderr and exits non-zero (I used 2). The script must be executable (`chmod +x`), print **only** JSON to stdout, and exit non-zero on any failure (an inventory script that prints an error and exits 0 produces an empty inventory and a green run that did nothing).

Scripts are simple and language-agnostic, but each invocation has no caching or configuration framework unless you build it.

## Option 2: an inventory plugin

An inventory plugin is Python code loaded by Ansible, configured by a small YAML file whose `plugin:` key names it:

```yaml
# cmdb.csv.yml
plugin: csvinv
csv_file: cmdb.csv
```

The class subclasses `BaseFileInventoryPlugin`, implements `verify_file` (decide whether this file is mine; mine requires the name ending `csv.yml`) and `parse`, which calls `self.inventory.add_host`, `add_group`, `add_child` and `set_variable`. Documented options (`DOCUMENTATION`) are read with `_read_config_data`. The graph and host variables were **identical** to the script's, and a test runs both through `ansible-inventory --list` and asserts the same hosts, groups and variables.

Measured differences worth knowing:

- Inventory plugins must be **enabled**: by default only built-in plugins are tried. I set `ANSIBLE_INVENTORY_ENABLED=script,csvinv,ini,yaml` and `ANSIBLE_INVENTORY_PLUGINS=./inventory_plugins` (in `ansible.cfg`: `[inventory] enable_plugins`).
- Strings set by the plugin with `set_variable` showed up in `--list` JSON as `{"__ansible_unsafe": "10.0.1.11"}`. As I understand the documentation, the marker means "untrusted text, do not template it": values from external inventory data are treated as unsafe so that a hostile CMDB entry such as `{{ lookup('pipe', ...) }}` cannot execute code (I did not test that scenario). For ordinary use you read them normally in playbooks (`{{ ansible_host }}`); my test unwraps the marker explicitly. The script form returned plain JSON values, since its output goes through a different path.
- A plugin can use the **inventory cache** (`cache: true`, with a cache plugin) to avoid hitting a slow API on every run.

## Cloud and other built-in inventory plugins

Collections provide plugins such as `amazon.aws.aws_ec2`, `azure.azcollection.azure_rm`, `google.cloud.gcp_compute`, `community.vmware.vmware_vm_inventory`, `kubernetes.core.k8s`. Their configuration files look like `plugin: amazon.aws.aws_ec2` with `regions`, `filters`, `keyed_groups` (create groups from tags) and `compose` (derive variables with Jinja2) sections. These are not run here; read the collection docs (`ansible-doc -t inventory -l` lists installed ones). Typical design:

- **Group by tag** (`keyed_groups: [{key: tags.role, prefix: role}]`) so a new instance joins `role_web` automatically.
- **Set `ansible_host`** from private IP or DNS with `compose`.
- **Filter** to the environment you intend (running against an unfiltered account inventory is how people change the wrong machines).
- **Cache** results (a few minutes) to speed up repeated runs, and refresh with `--flush-cache` when you have just created hosts.

## Combining static and dynamic

`-i` can be repeated, or `-i` can point at a directory containing several sources: static files for fixed infrastructure, a plugin config for the cloud. `group_vars/` next to the inventory directory apply to groups from any source, so you can attach variables to the `role_web` group created dynamically. That is the usual way to keep data in Git while membership is dynamic.

## Safety rules

1. **Fail loudly.** If the API is down, the inventory command must fail the run, not return an empty list.
2. **Never run against "all" in a dynamic inventory without a filter** or limit; `all` includes things you did not intend.
3. **Test the inventory like code**: assert expected groups exist and counts are sane (a pre-run check that fails if `prod` has zero hosts).
4. **Treat inventory data as untrusted input**: a tag or hostname written by someone else flows into variables. Keep `unsafe` handling on, and quote values used in shell commands.
5. **Be careful with secrets**: do not put them in dynamic inventory output, which can be logged.

## How It Actually Works

On start-up Ansible iterates the `-i` sources and tries each enabled inventory plugin in order, calling `verify_file` to let the plugin claim the source; the first plugin that accepts and parses it populates the in-memory inventory. The `script` plugin executes the file with `--list`, parses the JSON, and creates groups, hosts and (from `_meta`) host variables; without `_meta` it would call `--host` once per host, which is slow for big inventories. The `yaml` plugin handles YAML inventories, and a config file like `cmdb.csv.yml` is claimed by the plugin whose `verify_file` accepts it (mine accepts names ending `csv.yml`), which then reads its options from the file's `plugin:`, `csv_file:` keys. After parsing, `group_vars/` and `host_vars/` are layered on, then patterns and `--limit` select hosts. Because everything is assembled per run, there is no inventory state to sync, which is why a stale inventory is solved by re-running, not by repairing a file.

## Common mistakes

- **Scripts that exit 0 on error**, producing empty inventories.
- **Missing `_meta`**, so Ansible calls the script for every host.
- **Plugin not enabled**, then the config file is parsed as ordinary YAML and ignored.
- **No filter** on a cloud inventory.
- **Slow API calls on every run** with no cache.
- **Trusting inventory data in shell strings.**
- **Relying on host order** or on names that change.

## Exercise

1. Run `ansible-inventory -i src/l3/inventory_script.py --graph` and `--list`; then break the script (exit 0 with `{}`) and see what a playbook does.
2. Extend the CSV with a `zone` column, add `zone` as a group source in both forms, and update the tests.
3. Read `ansible-doc -t inventory -l` for your installed collections; pick one cloud plugin and write the config file for your environment, with a filter and `keyed_groups`.
4. Write a pre-run check that fails when any production group has fewer than two hosts.
