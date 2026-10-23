---
description: "Running Ansible as a service: controllers, AWX and AAP concepts, execution environments with ansible-builder, credentials, RBAC and isolation."
---

# 01 · Controllers, AWX and Execution Environments

On a laptop, `ansible-playbook` is enough. For a team it raises questions: who may run what against which hosts, where do credentials live, how do runs get scheduled and logged, and how do we make sure everybody uses the same Ansible version with the same collections? An **automation controller** answers those questions, and an **execution environment** pins the software.

!!! note "What was run, and what wasn't"
    **No automation controller was installed or run** (no AWX, no Ansible Automation Platform, no container runtime, no Kubernetes). The platform concepts below are from the Ansible and AWX documentation as I know it (October 2026); product details change quickly, so check current docs. What I *did* run: `ansible-builder` 3.2.0 to generate an execution environment build context (no container image was built or started).

## What a controller adds

| Capability | What it means |
|---|---|
| **Projects** | A link to a Git repository with playbooks; the controller syncs it before jobs |
| **Inventories** | Static or dynamic sources, with credentials for cloud syncs |
| **Credentials** | Encrypted stores for SSH keys, vault passwords, cloud tokens; users can *use* a credential without *seeing* it |
| **Job templates** | A saved combination: playbook + inventory + credentials + limit + extra vars + execution environment |
| **RBAC** | Who can run, edit, or read each template, inventory and credential |
| **Scheduling** | Cron-like runs, for drift audits and maintenance (Lesson 06) |
| **Workflows** | Chains of templates with success/failure branches and approval steps |
| **Logging and history** | Every run's output, who started it, with what parameters; usually an API and a UI |
| **API / CLI** | Trigger jobs from CI or other systems |
| **Execution isolation** | Jobs run in separate containers (execution environments) rather than on a shared shell |

AWX is the upstream open-source project; Red Hat's Ansible Automation Platform is the commercial product built on it. Open alternatives and supplements exist, and plain CI/CD systems (GitHub Actions, GitLab CI, Jenkins) can also run `ansible-playbook` (Lesson 02). The right choice depends on how much RBAC, credential isolation and scheduling you need versus how much infrastructure you want to run.

### The credential idea

The most valuable feature is separation: an operator can launch "Deploy web" without ever seeing the SSH key or vault password. The controller injects them into the job's container at run time. That turns "who has the production key?" from "everyone with the repo" into "the platform, and auditable use of it". It also makes the controller itself a high-value target: it holds credentials for the whole estate and needs hardening, backups, patching and monitoring (Lesson 07 treats incidents).

## Execution environments

An **execution environment (EE)** is a container image holding a specific `ansible-core`, `ansible-runner`, collections, Python libraries and system packages. The controller (or `ansible-navigator` on a laptop) runs each job inside an EE, so the same playbook runs with the same software everywhere, solving "works on my laptop".

`ansible-builder` builds EE images from a definition. My definition:

```yaml
version: 3
images:
  base_image:
    name: quay.io/fedora/fedora:42
dependencies:
  ansible_core:
    package_pip: ansible-core==2.21.5
  ansible_runner:
    package_pip: ansible-runner
  galaxy: requirements.yml
  python: requirements.txt
  system: bindep.txt
```

with `requirements.yml` listing `ansible.utils` 6.1.1, `requirements.txt` `netaddr==1.3.0`, and a `bindep.txt` for system packages. Running `ansible-builder create` produced a build context (`context/Dockerfile` and `context/_build/` with `bindep.txt`, `requirements.txt`, `requirements.yml` and helper scripts). The Dockerfile, which I read but could not build, has stages: a base stage that installs pip and `ansible-core==2.21.5 ansible-runner`, a galaxy stage that runs `ansible-galaxy collection install -r requirements.yml` into `/usr/share/ansible/collections`, a builder stage that compiles Python dependencies, and a final stage that copies the results. Observations:

- The pins from the definition appear literally in the image build, so the version of Ansible in the image is whatever you wrote: **EE definitions are the pinning mechanism** (the same advice as Level 2 · 06 for collections).
- The base image tag is mutable; pin by digest for reproducibility.
- Collection dependencies listed in `requirements.yml` are installed at build time, so a job never downloads collections at run time (faster, and works in air-gapped networks).
- Building requires a container runtime (Podman or Docker), which I did not have; so the image was never built and the Dockerfile was not tested.

Run an EE locally with `ansible-navigator run site.yml --execution-environment-image my-ee:1.0 -m stdout` (not run here) to replicate controller behaviour on a laptop. When EEs and a controller are used, remember: the playbook sees the **container's** filesystem and network; files on the host and SSH agent sockets are not available unless mounted or provided as credentials.

## Designing the project for a controller

1. **Repository layout** with a `playbooks/` directory, `roles/`, `collections/requirements.yml` and inventories in `inventories/<env>/`. The controller syncs the project and can install collections from `collections/requirements.yml` (if enabled).
2. **Parameterise with survey variables** rather than free text where possible (choices, ranges). Operators fill in a form; the template maps answers to `extra_vars`. Remember that `extra_vars` beat all other variables (Level 2 · 02), so any value an operator can set can override your safety checks. Validate inputs with `assert`.
3. **One template per operation**, with minimal credentials (for example "restart service" with a restricted account).
4. **Limits by default.** A template for production should require a `limit` or approval, and use the preflight idea from Lesson 07.
5. **Notifications** to chat/email on failure, and an external audit trail for production changes.
6. **Idempotent playbooks** so a retry is safe; the controller will retry or re-run.

## Operating the controller itself

- **Capacity:** each running job uses a container and some memory; the number of concurrent jobs and forks is bounded by controller nodes. Plan like a CI runner pool (CI/CD course, Level 4 · 02 on queue time).
- **High availability and backup:** the controller stores configuration in a database; back it up and test restores. A lost controller means lost credentials and job history.
- **Upgrades:** the controller, the EEs and the ansible-core in them have separate lifecycles. Test new EE images on non-production templates first.
- **Network position:** the controller reaches your entire estate and often internal APIs. Limit inbound access, use SSO and MFA, and treat it as tier-0 infrastructure.
- **Secrets lifecycle:** rotate credentials stored in the controller; consider short-lived credentials or external secret lookups (Lesson 03).
- **Auditing:** export job events; review who changed templates and credentials (CI/CD course, Level 4 · 05).

## When you do not need a controller

If you have a handful of operators and a CI system, running Ansible from CI with secrets stored in the CI vault and an EE or pinned virtualenv may be simpler: the pipeline provides scheduling, approvals and history, and you avoid another service. Move to a controller when you need credential separation for non-experts, self-service for other teams, or workflow orchestration across many templates. Whichever you choose, the playbooks stay the same.

## How It Actually Works

A controller keeps jobs as database records. When a job is launched, it checks out the project at a revision, resolves the inventory (possibly by running dynamic inventory plugins in an EE), creates a private directory with the project, inventory and an `env`/credentials bundle, and starts an **ansible-runner** process inside the EE container. Runner executes `ansible-playbook` with the requested options and streams structured events (each task start, result and stat) back as JSON, which the controller stores and displays live. Credentials are exposed to the process through temporary files and environment variables that exist only for the job's lifetime. This design is why the output in the UI is equivalent to the CLI output, why job isolation depends on the container runtime, and why an EE image is a hard dependency of every job.

## Common mistakes

- **Unpinned EEs**, so job behaviour changes without a commit.
- **Credentials that are too broad**, shared across all templates.
- **Surveys that accept free text** feeding shell commands.
- **No limit or approval** on production templates.
- **No backups** of the controller database.
- **Treating the controller as just another web app** instead of a tier-0 asset.
- **Running playbooks that depend on files on the operator's laptop.**

## Exercise

1. Write an `execution-environment.yml` for your project's collections and Python libraries and run `ansible-builder create`; read the generated Dockerfile and identify where each pin is applied.
2. Design the job templates and credentials for three operations (deploy, patch, rotate secrets): who may launch each, with which credential and which limits.
3. List what you must back up and monitor on a controller, and what the recovery time objective would be.
4. Decide, for a team of 8 with a CI system, whether a controller is justified. Write the argument both ways.
