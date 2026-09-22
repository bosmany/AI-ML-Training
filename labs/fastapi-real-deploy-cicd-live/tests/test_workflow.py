"""Static policy tests for assets/.github/workflows/deploy.yml."""

from conftest import assert_policy

from lab import lint


def test_workflow_triggers_on_push_to_main_only_never_pull_request(workflow):
    assert_policy(lint.check_workflow_triggers(workflow))


def test_token_permissions_are_least_privilege(workflow):
    assert_policy(lint.check_workflow_permissions(workflow))


def test_third_party_actions_are_pinned_to_a_version_or_sha(workflow):
    assert_policy(lint.check_actions_pinned(workflow))


def test_every_job_has_a_timeout(workflow):
    assert_policy(lint.check_job_timeouts(workflow))


def test_credentials_come_from_secrets_not_literals(workflow, workflow_text):
    assert_policy(lint.check_no_literal_secrets_in_workflow(workflow, workflow_text))


def test_deploy_runs_only_after_tests_pass(workflow):
    assert_policy(lint.check_deploy_runs_only_after_tests_pass(workflow))


def test_fly_api_token_comes_from_a_secret_not_a_literal(workflow):
    assert_policy(lint.check_fly_token_comes_from_secret(workflow))


def test_health_check_runs_after_deploy_and_retries(workflow):
    assert_policy(lint.check_health_check_runs_after_deploy(workflow))


def test_rollback_step_is_gated_on_failure_and_runs_after_deploy(workflow):
    assert_policy(lint.check_rollback_on_deploy_failure(workflow))
