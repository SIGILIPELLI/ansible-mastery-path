---
description: "Terraform and Ansible together: division of labour, handing outputs to an inventory, a tested output-to-inventory script, ordering and state pitfalls."
---

# 05 · Terraform and Ansible Together

Terraform (or OpenTofu) is good at creating infrastructure and tracking it in state. Ansible is good at configuring what runs on it, and at orchestrating operations. Using both is common, and the join between them is where problems arise: how does Ansible learn which machines Terraform created, and who owns what?

!!! note "What was run, and what wasn't"
    **Terraform was not installed**, so no `terraform apply` ran and no state was produced. I built and tested an inventory script that consumes the JSON shape produced by `terraform output -json` (as documented in the Terraform CLI docs), using a **hand-written** fixture. The Terraform-side snippets are untested illustrations. For Terraform itself, see the Terraform Mastery Path course on this site; for pipeline safety around plan and apply, the CI/CD Mastery Path (Level 3 · 05) covers a plan guard.

## Division of labour

| Concern | Better owned by | Why |
|---|---|---|
| Networks, VMs, load balancers, databases, DNS | Terraform | State, dependency graph, plan/diff, destroy |
| OS packages, config files, users, services on a host | Ansible | Fine-grained on-host modules, templates, handlers |
| Application deployment steps and orchestration | Ansible (or a deploy tool) | Ordering, batches, delegation |
| Bootstrapping (first boot) | cloud-init / images, then Ansible | The machine must exist and be reachable first |
| Secrets storage | A secret manager | Neither tool is a secret store |

The overlap: both can create cloud resources. Pick **one** owner per resource, or the two will fight (Level 3 · 08 conflicts). A decent rule: if the resource has an identity in a cloud API and a lifecycle independent of the OS, Terraform; if it is inside the OS, Ansible. Avoid having Ansible `cloud` modules and Terraform both manage security groups.

## The handoff patterns

1. **Output → inventory.** After `apply`, `terraform output -json` yields machine addresses; a script or inventory plugin turns them into Ansible hosts and groups. Static, simple, and explicit.
2. **Cloud inventory plugin.** Ansible queries the cloud API (`aws_ec2`, `azure_rm`, ...) for instances tagged `role=web`. Terraform tags instances; Ansible discovers by tag (Level 3 · 03). Decoupled from Terraform state, which is good when others create machines too.
3. **Terraform inventory provider/plugin.** A community plugin reads Terraform state directly (not run here). That couples Ansible to the state file and requires access to it; state may contain secrets, so restrict who can read it.
4. **Provisioner / `local-exec` calling `ansible-playbook`** from Terraform. Terraform's own docs advise provisioners as a last resort: failures leave resources tainted, the run is not part of the plan, and re-running configuration is awkward. Prefer a separate pipeline stage.
5. **User-data / `ansible-pull`** at first boot (Lesson 04): Terraform only needs to start instances with the right user-data; machines configure themselves.

## An output-to-inventory script, built and tested

`terraform output -json` prints an object whose keys are output names, each with `value`, `type` and `sensitive`. The script `tfinv.py` accepts that JSON and builds a script-protocol inventory (Level 3 · 03):

```json
{"web_ips": {"value": ["10.0.1.11", "10.0.1.12"], "type": ["tuple", ["string", "string"]], "sensitive": false},
 "db_hosts": {"value": "10.0.2.5", "type": "string", "sensitive": false}}
```

becomes hosts `web-01`, `web-02` (group `web`) and `db-01` (group `db`), each with `ansible_host` and a `tf_output` variable naming the source. `ansible-inventory -i ./tfinv.py --graph` (with `TFINV_FILE` set, because Ansible calls an inventory script with only `--list`) printed `@web: web-01, web-02` and `@db: db-01`. Design choices, each with a test (10 tests, all passing):

- **Refuse sensitive outputs.** If `"sensitive": true`, the script raises an error: addresses are not secrets, but anything marked sensitive should not be copied into an inventory, which can be logged.
- **An unknown or empty result is an error, not an empty inventory.** `{"other": ...}` gives `no known outputs found` and a non-zero exit. Silently returning zero hosts would make a downstream playbook succeed on nothing (Level 1 · 03: zero matching hosts exits 0).
- **Validate addresses** (non-empty strings).
- **Predictable names** (`web-01`...) that do not depend on the address, so changing an IP doesn't rename hosts.
- **Exit codes**: 0 on success, 1 on bad input, 2 on usage error; `--host` prints `{}`.
- It reads from a file named by `TFINV_FILE` or stdin. This is a teaching tool: real outputs would be richer (instance IDs, zones, tags).

Because the fixture is hand-written, the script has **never read an actual Terraform output**. If your Terraform version formats output differently from the documented shape, the tests will not tell you; run it once against a real `output -json` before relying on it.

## Ordering in a pipeline

```text
1. terraform plan   (PR: review the plan; guard destructive changes)
2. terraform apply  (protected branch; creates/updates machines)
3. wait for readiness (SSH reachable, cloud-init done)
4. ansible-playbook (configure; inventory from outputs or cloud tags)
5. smoke tests
```

Points that go wrong:

- **Readiness.** The instance exists but SSH is not ready. Use `wait_for_connection` or `wait_for` as the first task, with a timeout, rather than `sleep`.
- **Replaced machines.** If Terraform replaces an instance, its IP changes, host keys change (`host_key_checking` failures), and Ansible's configuration is gone; the playbook must re-run on the new machine. Make the Ansible run part of the same pipeline after each apply, and it must be idempotent so re-runs on unchanged machines are no-ops.
- **Drift between layers.** Terraform does not know what Ansible did and Ansible does not know what Terraform created beyond the inventory. Do not use Terraform to change files on machines and Ansible to resize disks.
- **Variables shared across tools.** Port numbers and names used in both should come from one place. Terraform can write a `vars.json`/`group_vars` file (via `local_file`) or Ansible can read Terraform outputs; keep a single source of truth.
- **Destroy order.** Before destroying machines that Ansible registered elsewhere (monitoring, load balancers, DNS), run a deregistration playbook; Terraform will not.
- **State access.** Anything reading state needs access to a sensitive file; prefer outputs (an explicit contract) over reading state.

## Idempotent infrastructure plus idempotent configuration

Both tools aim at convergence, but they differ in how they detect change: Terraform by comparing the plan with recorded state and refreshed real attributes, Ansible by inspecting the host. A full run of both after an unrelated change should produce no changes; that is a useful nightly test (a scheduled `terraform plan -detailed-exitcode` and an Ansible check run, Lesson 06).

## Alternatives and neighbours

- **Packer** builds machine images with Ansible as a provisioner: bake once, replace instead of patching. Terraform launches the image; Ansible runs only at build time and for rare tweaks.
- **Kubernetes** shifts configuration into manifests and controllers (GitOps, CI/CD course Level 3 · 06); Ansible still bootstraps nodes and manages out-of-cluster pieces.
- **Cloud-native config** (SSM, Run Command) can replace SSH-based pushes; Ansible has connection plugins and inventory plugins for some of these (not run here).

## How It Actually Works

Terraform writes its outputs from the state file after apply; `terraform output -json` reads them back as JSON without contacting the cloud. Ansible's inventory is evaluated at the start of each run, so it sees the machines that exist *then*. The script protocol runs the script with `--list` and parses the JSON. The inventory therefore is a snapshot taken at playbook start: if Terraform changes machines mid-run, Ansible does not notice. This one-way, snapshot-based coupling is a good thing: the only contract between the tools is data (a list of addresses and attributes), which you can validate, test, version and inspect, rather than shared mutable state.

## Common mistakes

- **Two tools managing the same resource.**
- **Provisioners as the main integration.**
- **Empty inventory silently accepted.**
- **Copying sensitive outputs into inventories or logs.**
- **Forgetting readiness waits.**
- **Reading the state file directly** instead of outputs.
- **No test of the join** between tools.

## Exercise

1. Run `pytest src/l4/test_tfinv.py` and add a new output (`bastion_ip`, group `bastion`) with tests for both list and string values.
2. If you have Terraform, run it for a trivial config with an `output` of a list, feed `terraform output -json` to `tfinv.py` and fix any difference from the fixture.
3. Write the pipeline outline (stages, credentials per stage, approvals) for apply then configure.
4. Decide who owns security groups, DNS records, OS firewall rules and application ports in your estate, and record it in one table.
