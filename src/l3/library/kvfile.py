#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import annotations

DOCUMENTATION = r"""
---
module: kvfile
short_description: Manage key=value entries in a simple settings file
description:
  - Ensures a C(key=value) line is present with the given value, or absent.
  - Idempotent, supports check mode and diff mode. Comments (lines starting with C(#)) and unrelated lines are preserved.
options:
  path:
    description: Settings file.
    type: path
    required: true
  key:
    description: Setting name (letters, digits, underscore, dot, dash).
    type: str
    required: true
  value:
    description: Setting value. Required when I(state=present).
    type: str
  state:
    description: Whether the key should exist.
    type: str
    choices: [present, absent]
    default: present
  create:
    description: Create the file when it does not exist.
    type: bool
    default: false
  mode:
    description: File mode applied after a change (for example C("0640")).
    type: raw
author:
  - Course example
"""

EXAMPLES = r"""
- kvfile: {path: /etc/app/app.conf, key: workers, value: "4"}
- kvfile: {path: /etc/app/app.conf, key: debug, state: absent}
"""

RETURN = r"""
before:
  description: Value before the call, or null.
  returned: always
  type: str
after:
  description: Value after the call, or null.
  returned: always
  type: str
"""

import os
import re

from ansible.module_utils.basic import AnsibleModule

KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def apply(lines, key, value, state):
    """Pure function: return (new_lines, before_value, after_value). Only the FIRST matching key is managed; duplicates are removed when present."""
    out, before, seen = [], None, False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            if k.strip() == key:
                if before is None:
                    before = v.strip()
                if state == "absent" or seen:
                    continue                      # drop the line (absent) or any duplicate
                seen = True
                out.append("%s=%s" % (key, value))
                continue
        out.append(line)
    if state == "present" and not seen:
        out.append("%s=%s" % (key, value))
    after = value if state == "present" else None
    return out, before, after


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type="path", required=True),
            key=dict(type="str", required=True),
            value=dict(type="str"),
            state=dict(type="str", default="present", choices=["present", "absent"]),
            create=dict(type="bool", default=False),
        ),
        required_if=[("state", "present", ["value"])],
        add_file_common_args=True,
        supports_check_mode=True,
    )
    p = module.params
    if not KEY_RE.match(p["key"]):
        module.fail_json(msg="invalid key %r" % p["key"])
    if p["value"] is not None and ("\n" in p["value"] or "\r" in p["value"]):
        module.fail_json(msg="value must not contain newlines")
    path = p["path"]
    exists = os.path.exists(path)
    if not exists and not p["create"]:
        if p["state"] == "absent":
            module.exit_json(changed=False, before=None, after=None)
        module.fail_json(msg="%s does not exist and create=false" % path)
    old_text = open(path).read() if exists else ""
    lines = old_text.splitlines()
    new_lines, before, after = apply(lines, p["key"], p["value"], p["state"])
    new_text = "\n".join(new_lines) + ("\n" if new_lines else "")
    changed = new_text != old_text
    diff = {"before": old_text, "after": new_text, "before_header": path, "after_header": path}
    if changed and not module.check_mode:
        tmp = path + ".kvtmp"
        with open(tmp, "w") as f:
            f.write(new_text)
        os.replace(tmp, path)
    file_args = module.load_file_common_arguments(module.params)
    if not module.check_mode and os.path.exists(path):
        changed = module.set_fs_attributes_if_different(file_args, changed)
    module.exit_json(changed=changed, before=before, after=after, diff=diff)


if __name__ == "__main__":
    main()
