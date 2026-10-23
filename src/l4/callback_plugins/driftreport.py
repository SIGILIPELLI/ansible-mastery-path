from __future__ import annotations

DOCUMENTATION = r"""
name: driftreport
type: aggregate
short_description: write a JSON drift report of changed, failed and unreachable tasks
description:
  - Collects every task result that is changed, failed or unreachable, with the diff when present, and writes one JSON file at the end of the run.
  - Intended for runs with C(--check --diff), where "changed" means "this host has drifted".
requirements:
  - enable in ansible.cfg (callbacks_enabled) or ANSIBLE_CALLBACKS_ENABLED
options:
  output_file:
    description: Where to write the report.
    env:
      - name: DRIFT_REPORT_FILE
    default: drift-report.json
"""

import json
import os
import time

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "driftreport"
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.findings = []
        self.hosts = set()
        self.started = time.time()
        self.check_mode = None

    def _record(self, kind, result):
        host = result._host.get_name()
        self.hosts.add(host)
        res = result._result
        item = {"host": host, "task": result._task.get_name(), "kind": kind}
        if "msg" in res and kind != "changed":
            item["msg"] = str(res["msg"])[:300]
        diffs = res.get("diff")
        if diffs:
            item["diff"] = diffs if isinstance(diffs, list) else [diffs]
        if res.get("results"):          # looped task: keep the label of items that changed
            item["items"] = [str(r.get("_ansible_item_label", r.get("item", ""))) for r in res["results"] if r.get("changed")]
        self.findings.append(item)

    def v2_runner_on_ok(self, result):
        self.hosts.add(result._host.get_name())
        if result._result.get("changed"):
            self._record("changed", result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._record("failed", result)

    def v2_runner_on_unreachable(self, result):
        self._record("unreachable", result)

    def v2_playbook_on_play_start(self, play):
        self.check_mode = bool(self._display and getattr(play, "_check_mode", False)) or self.check_mode

    def v2_playbook_on_stats(self, stats):
        summary = {h: stats.summarize(h) for h in sorted(stats.processed.keys())}
        report = {
            "check_mode": bool(self.check_mode),
            "seconds": round(time.time() - self.started, 2),
            "hosts": summary,
            "findings": self.findings,
            "drifted_hosts": sorted({f["host"] for f in self.findings if f["kind"] == "changed"}),
            "failed_hosts": sorted({f["host"] for f in self.findings if f["kind"] in ("failed", "unreachable")}),
        }
        path = os.environ.get("DRIFT_REPORT_FILE", "drift-report.json")
        with open(path, "w") as fh:
            json.dump(report, fh, indent=2, sort_keys=True, default=str)
