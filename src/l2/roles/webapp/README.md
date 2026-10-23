# webapp

Renders `webapp.conf` into `webapp_root` and notifies the `Reload webapp` handler when it changes.

| Variable | Default | Meaning |
|---|---|---|
| `webapp_port` | `8080` | Listen port (1-65535) |
| `webapp_workers` | `2` | Worker count (>= 1) |
| `webapp_root` | `<sandbox>/<inventory_hostname>` | Directory for the config file |
