from nologlint import lint_text, secret_vars
def L(y): return lint_text(y)
BAD = """
- name: p
  hosts: all
  tasks:
    - name: write secret
      ansible.builtin.copy: {dest: /x, content: "{{ db_password }}"}
"""
def test_flags_secret_without_no_log(): assert len(L(BAD)) == 1 and L(BAD)[0][2] == ["db_password"]
def test_no_log_on_task_clears(): assert L(BAD.replace("{dest", "{dest").replace("content: \"{{ db_password }}\"}", "content: \"{{ db_password }}\"}\n      no_log: true")) == []
def test_no_log_on_block_covers_children():
    y = "- hosts: all\n  tasks:\n    - block:\n        - ansible.builtin.copy: {dest: /x, content: '{{ api_token }}'}\n      no_log: true\n"; assert L(y) == []
def test_nested_block_without_no_log_flagged():
    y = "- hosts: all\n  tasks:\n    - block:\n        - ansible.builtin.copy: {dest: /x, content: '{{ api_token }}'}\n"; assert len(L(y)) == 1
def test_play_level_no_log_covers_all():
    y = "- hosts: all\n  no_log: true\n  tasks:\n    - ansible.builtin.copy: {dest: /x, content: '{{ vault_x }}'}\n"; assert L(y) == []
def test_debug_flagged_even_with_no_log_false_positive_guard():
    y = "- hosts: all\n  tasks:\n    - ansible.builtin.debug: {msg: '{{ db_password }}'}\n      no_log: true\n"; assert L(y)[0][3] == "debug prints it"
def test_non_secret_names_ignored(): assert L("- hosts: all\n  tasks:\n    - ansible.builtin.copy: {dest: /x, content: '{{ app_name }}'}\n") == []
def test_vault_prefix_is_secret(): assert secret_vars("{{ vault_db }}") == {"vault_db"}
def test_secret_in_filter_expression(): assert secret_vars("{{ db_password | b64encode }}") == {"db_password"}
def test_secret_in_environment_flagged():
    y = "- hosts: all\n  tasks:\n    - ansible.builtin.command: run\n      environment: {TOKEN: '{{ api_token }}'}\n"; assert len(L(y)) == 1
def test_literal_word_without_jinja_not_flagged(): assert L("- hosts: all\n  tasks:\n    - ansible.builtin.copy: {dest: /x, content: 'password policy'}\n") == []
def test_handlers_checked():
    y = "- hosts: all\n  tasks: []\n  handlers:\n    - name: h\n      ansible.builtin.copy: {dest: /x, content: '{{ secret_key }}'}\n"; assert len(L(y)) == 1
