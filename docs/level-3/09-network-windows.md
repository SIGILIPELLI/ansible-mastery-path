---
description: "Ansible beyond Linux servers: Windows over WinRM or PSRP, network devices over network_cli, connection types and collections read offline."
---

# 09 · Network and Windows Targets

Ansible manages more than Linux servers over SSH. Windows hosts, switches, routers and firewalls, cloud APIs and appliances each need a different **connection plugin** and a set of modules designed for them. Because the model is "run a task, get JSON", the playbook language stays the same; what changes is where and how the work executes.

!!! note "What was run, and what wasn't"
    **No Windows host, network device or API endpoint was available, so nothing in this lesson was executed against such a target.** What I did do: install the `ansible.windows` (3.9.1) and `ansible.netcommon` (8.7.1) collections from Galaxy, count their modules with `ansible-doc`, read module documentation offline, and list the connection plugins. Everything about behaviour on real devices is from the Ansible documentation (October 2026) and general knowledge; read it as a map for where to look, not as tested advice.

## What the collections contain

```text
$ ansible-doc -l ansible.windows | wc -l
      81
$ ansible-doc -l ansible.netcommon | wc -l
      16
$ ansible-doc ansible.windows.win_copy | head -5
> MODULE ansible.windows.win_copy (.../ansible/windows/plugins/modules/win_copy.py)
  The `win_copy' module copies a file on the local box to remote windows locations.
  For non-Windows targets, use the [ansible.builtin.copy] module instead.
```

`ansible.windows` supplies **81** modules on this version (that is the number of lines `ansible-doc -l` printed; I did not check whether it also lists plugins), prefixed `win_` (`win_copy`, `win_file`, `win_service`, `win_feature`, `win_user`, `win_registry`, `win_shell`, `win_package` ...). `ansible.netcommon` listed **16** entries (generic network modules such as `cli_command`, `cli_config`, `netconf_config`; its connection plugins are listed separately by `ansible-doc -t connection -l`). Vendor collections (Cisco, Juniper, Arista, Palo Alto, F5 ...) add resource modules for their devices. The connection plugins visible with `ansible-doc -t connection -l` included `ansible.builtin.winrm`, `ansible.builtin.psrp`, `ansible.builtin.ssh`, `ansible.builtin.local`, `ansible.netcommon.network_cli`, `netconf`, `httpapi` and `libssh`.

## Windows

Two protocols are supported for managing Windows from a control node (the control node itself must be Linux or macOS; Windows is not supported as a controller for the full tool, per the docs):

- **WinRM** (`ansible_connection=winrm`): Windows Remote Management over HTTP(S), using the `pywinrm` Python library on the controller. Authentication options include NTLM, Kerberos and certificate/basic with HTTPS; Kerberos is the common choice in domains and needs system libraries on the controller.
- **PSRP** (`ansible_connection=psrp`): PowerShell Remoting Protocol, a library (`pypsrp`) with generally better performance for file transfer.
- **SSH** on Windows is supported by newer builds of Windows with OpenSSH enabled (`ansible_shell_type: powershell` or `cmd`).

Typical inventory variables:

```ini
[windows]
win01 ansible_host=10.0.3.10
[windows:vars]
ansible_connection=winrm
ansible_winrm_transport=ntlm
ansible_winrm_server_cert_validation=validate
ansible_user=svc_ansible
ansible_password={{ vault_win_password }}      # from a vaulted variable
```

(An example only; not run.) Differences to expect:

- Modules are PowerShell scripts, named `win_*`; most Linux modules do not work. Check the module list for the equivalent.
- Paths use backslashes and drive letters; in YAML, quote or double them (`'C:\Temp'`).
- File ownership and modes are ACL-based, not POSIX modes.
- `become` uses `runas`, with different semantics from `sudo`.
- Reboots are common (`ansible.windows.win_reboot`), and the connection drops, so wait for it to return.
- Fact gathering uses `ansible.windows.win_setup` or the same `setup` entry point; the fact names differ (`ansible_os_family: Windows`).
- Credentials and certificates are the main operational risk: WinRM over plain HTTP with basic authentication sends credentials in clear text; use HTTPS and a modern transport.

## Network devices

Network devices usually cannot run Python modules, so Ansible's network model runs modules **on the controller**, which connects to the device (via CLI over SSH, NETCONF, or an HTTP API) and parses/sends commands:

- **`network_cli`**: SSH to a CLI, sending commands and reading text. Set `ansible_connection=ansible.netcommon.network_cli` and `ansible_network_os=<platform>` (for example `cisco.ios.ios`).
- **`netconf`**: NETCONF over SSH with XML, for devices that support it.
- **`httpapi`**: REST-style APIs (Arista eAPI, others).

Typical group variables:

```yaml
# group_vars/switches.yml
ansible_connection: ansible.netcommon.network_cli
ansible_network_os: cisco.ios.ios
ansible_user: netops
ansible_become: true
ansible_become_method: enable
```

Concepts that matter:

1. **Resource modules** (for example `ios_interfaces`, `ios_vlans`) manage a *section of configuration as structured data* with states such as `merged`, `replaced`, `overridden`, `deleted`, `gathered`, `rendered`, `parsed`. They are idempotent by comparing the structured data to the device's current configuration. `merged` adds, `replaced` makes a resource match exactly, `overridden` makes the whole device section match exactly (and deletes anything not listed, which is the dangerous one). `gathered` reads the config into the same structured format, useful to bootstrap source-of-truth data.
2. **Generic command modules** (`cli_command`, `ios_command`, `ios_config`) send text commands; they are the escape hatch and have the same idempotency issues as `command` and `shell` (Lesson 04). `ios_config` can compare the intended lines against the running config.
3. **Parsing**: network output is text. `ansible.utils.cli_parse` and parsers like TextFSM, TTP or `xmltodict` turn it into data. Those need extra Python libraries on the controller (the same dependency lesson as Lesson 03 and Level 2 · 06).
4. **Persistent connections**: since each task would otherwise log in again, Ansible keeps a persistent connection process (`ansible-connection`) per host with a timeout (`persistent_command_timeout`), so a long-running task can fail with a timeout error that does not appear on servers.
5. **Check mode and diff** are supported by many network modules (they can compute the config diff, and some devices can "commit confirmed" for a safe rollback), which makes them natural candidates for staged changes. Whether yours does depends on the platform and module.
6. **Safety**: a network change can cut off your own management access. Use out-of-band access, `commit confirmed` or rollback timers where the platform has them, and apply changes to one device (a `--limit`, Level 2 · 07) before the fleet. Back up configurations before change (`*_config` with `backup: true`).

## APIs and "localhost" modules

Many modules (cloud providers, SaaS, Kubernetes, load balancers) run on the **controller** against an API, with `hosts: localhost` and `connection: local` (or delegated). Credentials, rate limits and API pagination matter more than SSH. The same principles hold: use modules that take `state`, register results, check mode where supported, and `no_log` for tokens.

## Choosing the connection and keeping inventory clear

- Put connection details in `group_vars` for the group (windows, switches), not on every host.
- Test connectivity with the right ping module: `ansible.windows.win_ping`, `ansible.netcommon.net_ping`/vendor equivalents, `ansible.builtin.ping` for Linux. (I confirmed `win_copy`'s docs offline; I did not run `win_ping`.)
- Keep the Python libraries needed by each connection (`pywinrm`, `pypsrp`, `ncclient`, `paramiko`/`ansible-pylibssh`) pinned in your requirements and in the execution environment (Level 4 · 01).
- Write per-platform roles with a common interface (`role: ntp` with variables) and platform task files, rather than one role full of `when: os == ...`.

## Why this is mostly "the same Ansible"

The playbook, inventory, variables, handlers, roles and templates work identically. The differences concentrate in four places: the connection plugin, the module set, the facts, and the failure modes (timeouts, authentication, reboots, device quirks). If you can reason about idempotency, check mode and blast radius on servers, you can reason about them for network gear; what you need to learn is each platform's resource model and how it is safely changed.

## How It Actually Works

For servers, the controller ships a module to the target and runs it there. For network devices and APIs, there is no place to run Python on the target, so the module runs **on the controller** inside a persistent-connection helper: the connection plugin (`network_cli`, `httpapi`, `netconf`) opens a long-lived session to the device in a separate process and exposes a socket to the module worker. The module sends commands over that socket, receives text or structured data, and returns JSON. For Windows, the module is a PowerShell script (or C# in newer ones) sent to the host over WinRM or PSRP and executed there by PowerShell, and its JSON output is returned. Task scheduling, variables and templating on the controller are unchanged in every case.

## Common mistakes

- **Using Linux modules on Windows** (or the reverse).
- **WinRM over HTTP with basic auth** in production.
- **`overridden` state on a network resource** without a preview.
- **No out-of-band access** when changing network config.
- **Persistent-connection timeouts** misdiagnosed as device failures.
- **Missing Python libraries** for the connection or parser.
- **Putting device credentials in plain inventory** instead of Vault or a secrets lookup.

## Exercise

1. Install `ansible.windows` and `ansible.netcommon` and use `ansible-doc` to find the module that manages (a) Windows services, (b) Windows registry keys, (c) a generic CLI command on a network device. Read each one's `state` options.
2. Write the `group_vars` for a Windows group and a switch group, with credentials from a vaulted file.
3. Explain, for a network resource module, the difference between `merged`, `replaced` and `overridden` using a three-line example config.
4. Draft the rollout plan for changing an interface description on 40 switches: pre-checks, backup, canary, `--check --diff`, batches, verification, rollback.
