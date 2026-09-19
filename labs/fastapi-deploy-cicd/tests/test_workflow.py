"""Static policy tests for assets/.github/workflows/ci.yml."""

from conftest import assert_policy

from lab import lint


def test_workflow_runs_on_push_and_pull_request_but_not_pull_request_target(workflow):
    assert_policy(lint.check_workflow_triggers(workflow))


def test_token_permissions_are_least_privilege(workflow):
    assert_policy(lint.check_workflow_permissions(workflow))


def test_third_party_actions_are_pinned_to_a_version_or_sha(workflow):
    assert_policy(lint.check_actions_pinned(workflow))


def test_tests_must_pass_before_the_image_is_built(workflow):
    assert_policy(lint.check_tests_run_before_image_build(workflow))


def test_pip_dependencies_are_cached(workflow):
    assert_policy(lint.check_pip_cache(workflow))


def test_credentials_come_from_secrets_not_literals(workflow, workflow_text):
    assert_policy(lint.check_no_literal_secrets_in_workflow(workflow, workflow_text))


def test_every_job_has_a_timeout(workflow):
    assert_policy(lint.check_job_timeouts(workflow))


def test_images_are_not_pushed_from_pull_requests(workflow):
    assert_policy(lint.check_push_is_guarded(workflow))
