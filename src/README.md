# Course code

Everything in the lessons is here and was run with ansible-core 2.21.5 on macOS (Python 3.14).

```bash
python3 -m venv .venv && .venv/bin/pip install -r src/requirements.txt
.venv/bin/ansible-galaxy collection install -r src/requirements.yml -p src/l3/collections   # only needed for the collection lessons
.venv/bin/python -m pytest -q src/baseline src/l2 src/l3 src/l4   # takes a few minutes; many tests start real Ansible runs
```

Several playbooks and inventories contain an absolute path to the author's virtual environment (`/private/tmp/claude-501/ans/bin/python`) in `ansible_python_interpreter`; the tests rewrite it to the running interpreter, but when you run a playbook by hand, edit it to your own Python.
