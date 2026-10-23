from __future__ import annotations

DOCUMENTATION = r"""
name: csvinv
short_description: inventory from a CSV file
description:
  - Reads a CSV with columns name,address,role,env,port and builds hosts and groups (role and env).
options:
  plugin:
    description: Must be csvinv.
    required: true
    choices: [csvinv]
  csv_file:
    description: Path to the CSV (relative to the inventory source file).
    required: true
    type: str
"""

import csv
import os

from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseFileInventoryPlugin


class InventoryModule(BaseFileInventoryPlugin):
    NAME = "csvinv"

    def verify_file(self, path):
        return super().verify_file(path) and path.endswith(("csv.yml", "csv.yaml"))

    def parse(self, inventory, loader, path, cache=True):
        super().parse(inventory, loader, path, cache)
        config = self._read_config_data(path)
        csv_path = os.path.join(os.path.dirname(path), config["csv_file"])
        try:
            fh = open(csv_path, newline="")
        except OSError as exc:
            raise AnsibleParserError("csvinv: cannot open %s: %s" % (csv_path, exc))
        with fh:
            for row in csv.DictReader(fh):
                self.inventory.add_host(row["name"])
                for g in (row["role"], row["env"]):
                    self.inventory.add_group(g)
                    self.inventory.add_child(g, row["name"])
                self.inventory.set_variable(row["name"], "ansible_host", row["address"])
                self.inventory.set_variable(row["name"], "http_port", int(row["port"]))
                self.inventory.set_variable(row["name"], "ansible_connection", "local")
