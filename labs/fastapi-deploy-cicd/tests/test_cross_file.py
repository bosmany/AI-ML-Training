"""Consistency between the files: what CI tests is what ships, and compose matches the image."""

from conftest import assert_policy

from lab import lint


def test_ci_tests_on_the_same_python_version_as_the_image(dockerfile, workflow):
    assert_policy(lint.check_python_versions_match(dockerfile, workflow))


def test_dockerfile_port_and_compose_port_and_health_path_agree(dockerfile, compose):
    assert_policy(lint.check_health_path_and_port_agree(dockerfile, compose))
