from __future__ import annotations

from ansible.errors import AnsibleFilterError


def human_bytes(value, base=1024):
    """Format a byte count: 1536 -> '1.5 KiB'. Raises AnsibleFilterError for non-numbers and negatives."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise AnsibleFilterError("human_bytes expects a number, got %r" % (value,))
    if n < 0:
        raise AnsibleFilterError("human_bytes expects a non-negative number, got %r" % (value,))
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    i = 0
    while n >= base and i < len(units) - 1:
        n /= base
        i += 1
    return ("%d %s" % (n, units[i])) if i == 0 else ("%.1f %s" % (n, units[i]))


def kv_to_dict(text, sep="="):
    """Parse 'a=1\\nb=2' lines into a dict, ignoring blank lines and # comments."""
    out = {}
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if sep not in line:
            raise AnsibleFilterError("kv_to_dict: line without %r: %r" % (sep, raw))
        k, _, v = line.partition(sep)
        out[k.strip()] = v.strip()
    return out


def mask_secrets(mapping, words=("password", "secret", "token", "key")):
    """Return a copy of a (possibly nested) dict with values of sensitive-looking keys replaced by ********."""
    if isinstance(mapping, dict):
        return {k: ("********" if any(w in str(k).lower() for w in words) else mask_secrets(v, words)) for k, v in mapping.items()}
    if isinstance(mapping, list):
        return [mask_secrets(v, words) for v in mapping]
    return mapping


class FilterModule(object):
    def filters(self):
        return {"human_bytes": human_bytes, "kv_to_dict": kv_to_dict, "mask_secrets": mask_secrets}
