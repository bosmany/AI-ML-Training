"""Static policy tests for assets/fly.toml (parsed with tomllib; nothing is deployed)."""

from conftest import assert_policy

from lab import lint


def test_fly_toml_declares_an_app_name(fly_toml):
    assert_policy(lint.check_fly_app_name_set(fly_toml))


def test_fly_toml_declares_a_primary_region(fly_toml):
    assert_policy(lint.check_fly_primary_region_set(fly_toml))


def test_http_service_sets_internal_port_and_forces_https(fly_toml):
    assert_policy(lint.check_fly_http_service_config(fly_toml))


def test_http_service_has_a_health_check_on_the_health_path(fly_toml):
    assert_policy(lint.check_fly_healthcheck_configured(fly_toml))


def test_vm_resources_are_declared_explicitly(fly_toml):
    assert_policy(lint.check_fly_vm_resources_declared(fly_toml))


def test_no_secrets_are_baked_into_fly_toml(fly_toml, fly_toml_text):
    assert_policy(lint.check_fly_toml_has_no_baked_secrets(fly_toml, fly_toml_text))
