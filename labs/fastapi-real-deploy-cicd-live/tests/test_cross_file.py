"""Consistency between the files: the workflow must deploy and health-check the app fly.toml declares."""

from conftest import assert_policy

from lab import lint


def test_health_check_targets_the_app_declared_in_fly_toml(fly_toml, workflow):
    assert_policy(lint.check_health_check_targets_fly_app(fly_toml, workflow))
