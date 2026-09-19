"""``python -m lab`` runs every policy check against your files and prints a report."""

from __future__ import annotations

import sys

from lab import lint
from lab.compose import load_compose
from lab.dockerfile import parse_dockerfile
from lab.dockerignore import parse_dockerignore
from lab.errors import AssetError
from lab.loader import COMPOSE, DOCKERFILE, DOCKERIGNORE, WORKFLOW, read_asset
from lab.workflow import load_workflow


def main() -> int:
    total = 0
    try:
        dockerfile_text = read_asset(DOCKERFILE)
        df = parse_dockerfile(dockerfile_text)
        patterns = parse_dockerignore(read_asset(DOCKERIGNORE))
        compose = load_compose(read_asset(COMPOSE))
        workflow_text = read_asset(WORKFLOW)
        workflow = load_workflow(workflow_text)
    except AssetError as exc:
        print(f"FAIL  {exc}")
        return 1
    checks = {
        "Dockerfile": [
            lint.check_multi_stage(df), lint.check_pinned_base_images(df), lint.check_non_root_user(df),
            lint.check_healthcheck(df), lint.check_no_baked_secrets(df, dockerfile_text),
            lint.check_cache_friendly_layer_order(df), lint.check_pip_no_cache(df),
            lint.check_exec_form_command(df), lint.check_python_runtime_env(df),
            lint.check_exposed_port_and_bind_address(df),
        ],
        ".dockerignore": [
            lint.check_dockerignore_has_sensible_entries(patterns), lint.check_dockerignore_keeps_build_inputs(patterns),
        ],
        "docker-compose.yml": [
            lint.check_compose_builds_api_from_dockerfile(compose), lint.check_compose_healthchecks(compose),
            lint.check_compose_depends_on_healthy(compose), lint.check_compose_secrets_via_variables(compose),
            lint.check_compose_images_pinned(compose), lint.check_compose_restart_policy(compose),
            lint.check_compose_port_from_variable(compose),
        ],
        "ci.yml": [
            lint.check_workflow_triggers(workflow), lint.check_workflow_permissions(workflow),
            lint.check_actions_pinned(workflow), lint.check_tests_run_before_image_build(workflow),
            lint.check_pip_cache(workflow), lint.check_no_literal_secrets_in_workflow(workflow, workflow_text),
            lint.check_job_timeouts(workflow), lint.check_push_is_guarded(workflow),
        ],
    }
    for name, results in checks.items():
        problems = [p for result in results for p in result]
        total += len(problems)
        print(f"{'OK  ' if not problems else 'FAIL'}  {name}")
        for problem in problems:
            print(f"        - {problem}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
