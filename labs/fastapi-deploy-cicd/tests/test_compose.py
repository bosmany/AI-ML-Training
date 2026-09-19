"""Static policy tests for assets/docker-compose.yml (parsed with PyYAML; nothing is started)."""

from conftest import assert_policy

from lab import lint


def test_api_service_is_built_from_the_local_dockerfile(compose):
    assert_policy(lint.check_compose_builds_api_from_dockerfile(compose))


def test_every_service_declares_a_healthcheck(compose):
    assert_policy(lint.check_compose_healthchecks(compose))


def test_api_waits_for_dependencies_to_be_healthy_not_just_started(compose):
    assert_policy(lint.check_compose_depends_on_healthy(compose))


def test_secrets_come_from_variables_never_literals(compose):
    assert_policy(lint.check_compose_secrets_via_variables(compose))


def test_third_party_images_are_pinned(compose):
    assert_policy(lint.check_compose_images_pinned(compose))


def test_services_have_a_restart_policy(compose):
    assert_policy(lint.check_compose_restart_policy(compose))


def test_published_port_is_configurable_through_a_variable(compose):
    assert_policy(lint.check_compose_port_from_variable(compose))
