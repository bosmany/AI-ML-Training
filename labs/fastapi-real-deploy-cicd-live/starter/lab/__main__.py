"""``python -m lab`` runs every policy check against your files and prints a report."""

from __future__ import annotations

import sys

from lab import lint
from lab.errors import AssetError
from lab.flytoml import load_fly_toml
from lab.loader import FLY_TOML, WORKFLOW, read_asset
from lab.workflow import load_workflow


def main() -> int:
    total = 0
    try:
        fly_text = read_asset(FLY_TOML)
        fly = load_fly_toml(fly_text)
        workflow_text = read_asset(WORKFLOW)
        workflow = load_workflow(workflow_text)
    except AssetError as exc:
        print(f"FAIL  {exc}")
        return 1
    checks = {
        "fly.toml": [
            lint.check_fly_app_name_set(fly), lint.check_fly_primary_region_set(fly),
            lint.check_fly_http_service_config(fly), lint.check_fly_healthcheck_configured(fly),
            lint.check_fly_vm_resources_declared(fly), lint.check_fly_toml_has_no_baked_secrets(fly, fly_text),
        ],
        ".github/workflows/deploy.yml": [
            lint.check_workflow_triggers(workflow), lint.check_workflow_permissions(workflow),
            lint.check_actions_pinned(workflow), lint.check_job_timeouts(workflow),
            lint.check_no_literal_secrets_in_workflow(workflow, workflow_text),
            lint.check_deploy_runs_only_after_tests_pass(workflow), lint.check_fly_token_comes_from_secret(workflow),
            lint.check_health_check_runs_after_deploy(workflow), lint.check_rollback_on_deploy_failure(workflow),
        ],
        "fly.toml <-> deploy.yml": [
            lint.check_health_check_targets_fly_app(fly, workflow),
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
