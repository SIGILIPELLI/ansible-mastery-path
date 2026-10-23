#!/usr/bin/env bash
# CI pipeline for an Ansible repository: cheapest checks first, stop at the first failure.
# Usage: ci.sh <playbook> <inventory> [extra ansible-playbook args...]   (run from the repo root; PATH must contain the pinned venv)
set -euo pipefail
PB=${1:?playbook}; INV=${2:?inventory}; shift 2
step() { printf '\n== %s\n' "$*"; }
recap_changed() { grep -E '^[A-Za-z0-9_.-]+ +:' | sed -E 's/.*changed=([0-9]+).*/\1/' | paste -sd+ - | bc; }

step "1 syntax-check";                 ansible-playbook -i "$INV" "$PB" --syntax-check "$@" >/dev/null
step "2 ansible-lint";                 ansible-lint "$PB"
step "3 secret hygiene (no_log)";      python3 "$(dirname "$0")/nologlint.py" "$PB"
step "4 converge (first run)";         ansible-playbook -i "$INV" "$PB" "$@" | tee /tmp/ci_run1.txt | grep -E '^[A-Za-z0-9_.-]+ +:' || true
step "5 idempotence (second run)";     ansible-playbook -i "$INV" "$PB" "$@" | tee /tmp/ci_run2.txt | grep -E '^[A-Za-z0-9_.-]+ +:' || true
CH=$(recap_changed < /tmp/ci_run2.txt); [ "${CH:-0}" = "0" ] || { echo "FAIL: second run reported $CH change(s)"; exit 1; }
step "6 check mode shows no drift";    ansible-playbook -i "$INV" "$PB" --check "$@" | tee /tmp/ci_run3.txt | grep -E '^[A-Za-z0-9_.-]+ +:' || true
CH=$(recap_changed < /tmp/ci_run3.txt); [ "${CH:-0}" = "0" ] || { echo "FAIL: check mode reported $CH change(s)"; exit 1; }
echo; echo "CI OK"
