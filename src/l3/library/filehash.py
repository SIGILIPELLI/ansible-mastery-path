#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import annotations

DOCUMENTATION = r"""
---
module: filehash
short_description: Report the hash and size of a file
description:
  - Read-only module that returns the hexadecimal digest and size of a file on the managed host.
options:
  path:
    description: File to hash.
    type: path
    required: true
  algorithm:
    description: Hash algorithm.
    type: str
    choices: [sha256, sha1, md5]
    default: sha256
author:
  - Course example
"""

EXAMPLES = r"""
- name: Hash the config
  filehash:
    path: /etc/app/app.conf
  register: h
"""

RETURN = r"""
digest:
  description: Hex digest of the file content.
  returned: success
  type: str
size:
  description: Size in bytes.
  returned: success
  type: int
"""

import hashlib
import os

from ansible.module_utils.basic import AnsibleModule


def compute(path, algorithm):
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest(), os.path.getsize(path)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type="path", required=True),
            algorithm=dict(type="str", default="sha256", choices=["sha256", "sha1", "md5"]),
        ),
        supports_check_mode=True,
    )
    path = module.params["path"]
    if not os.path.isfile(path):
        module.fail_json(msg="file not found or not a regular file: %s" % path, path=path)
    try:
        digest, size = compute(path, module.params["algorithm"])
    except OSError as exc:
        module.fail_json(msg="cannot read %s: %s" % (path, exc), path=path)
    module.exit_json(changed=False, digest=digest, size=size, path=path)


if __name__ == "__main__":
    main()
