#!/usr/bin/env python3
"""Executable vault password source: prints the password taken from an environment variable (as a CI system would inject it). Exit non-zero when it is missing."""
import os, sys
pw = os.environ.get("ANSIBLE_VAULT_CI_PASSWORD", "")
if not pw:
    print("vault_pass: ANSIBLE_VAULT_CI_PASSWORD is not set", file=sys.stderr); sys.exit(1)
print(pw)
