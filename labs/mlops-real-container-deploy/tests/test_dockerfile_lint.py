"""Static policy tests for assets/Dockerfile (no Docker needed - these run in milliseconds)."""

from conftest import assert_policy

from lab import lint


def test_dockerfile_uses_a_multi_stage_build(dockerfile):
    assert_policy(lint.check_multi_stage(dockerfile))


def test_every_base_image_is_pinned_to_a_version_tag_not_latest(dockerfile):
    assert_policy(lint.check_pinned_base_images(dockerfile))


def test_container_runs_as_a_non_root_user(dockerfile):
    assert_policy(lint.check_non_root_user(dockerfile))


def test_healthcheck_calls_the_health_endpoint(dockerfile):
    assert_policy(lint.check_healthcheck(dockerfile))


def test_no_secrets_are_baked_into_the_image(dockerfile, dockerfile_text):
    assert_policy(lint.check_no_baked_secrets(dockerfile, dockerfile_text))


def test_requirements_are_copied_and_installed_before_the_source_for_layer_caching(dockerfile):
    assert_policy(lint.check_cache_friendly_layer_order(dockerfile))


def test_pip_install_does_not_keep_its_download_cache(dockerfile):
    assert_policy(lint.check_pip_no_cache(dockerfile))


def test_start_command_uses_exec_form_so_sigterm_reaches_uvicorn(dockerfile):
    assert_policy(lint.check_exec_form_command(dockerfile))


def test_python_output_is_unbuffered_and_no_bytecode_is_written(dockerfile):
    assert_policy(lint.check_python_runtime_env(dockerfile))


def test_port_is_exposed_and_uvicorn_binds_all_interfaces(dockerfile):
    assert_policy(lint.check_exposed_port_and_bind_address(dockerfile))
