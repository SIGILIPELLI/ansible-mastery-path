from __future__ import annotations

DOCUMENTATION = r"""
name: envfile
short_description: read a KEY=VALUE file on the controller
description:
  - Returns the value for each requested key from a dotenv-style file. Runs on the controller, not the target.
options:
  _terms:
    description: Keys to look up.
    required: true
  file:
    description: Path to the file.
    type: path
    required: true
  default:
    description: Value for a missing key. If unset a missing key is an error.
"""

from ansible.errors import AnsibleLookupError
from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)
        path = self.get_option("file")
        try:
            with open(path) as f:
                data = {}
                for raw in f:
                    line = raw.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        data[k.strip()] = v.strip().strip('"').strip("'")
        except OSError as exc:
            raise AnsibleLookupError("envfile: cannot read %s: %s" % (path, exc))
        out = []
        for key in terms:
            if key in data:
                out.append(data[key])
            elif self.get_option("default") is not None:
                out.append(self.get_option("default"))
            else:
                raise AnsibleLookupError("envfile: key %r not in %s" % (key, path))
        return out
