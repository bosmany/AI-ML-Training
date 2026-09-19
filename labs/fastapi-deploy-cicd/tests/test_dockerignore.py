"""Static policy tests for assets/.dockerignore."""

from conftest import assert_policy

from lab import lint


def test_dockerignore_excludes_git_env_files_virtualenvs_and_bytecode(ignore_patterns):
    assert_policy(lint.check_dockerignore_has_sensible_entries(ignore_patterns))


def test_dockerignore_does_not_exclude_files_the_build_needs(ignore_patterns):
    assert_policy(lint.check_dockerignore_keeps_build_inputs(ignore_patterns))
