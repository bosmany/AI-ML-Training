"""The command line, driven through ``main(argv) -> int`` against a real SQLite file."""

from __future__ import annotations

import pytest

from lab.cli import main


@pytest.fixture
def cli(db_path, capsys):
    def run(*argv: str) -> tuple[int, str, str]:
        code = main(["--db", str(db_path), *argv])
        captured = capsys.readouterr()
        return code, captured.out.strip(), captured.err.strip()

    return run


def finished_run(cli, acc: str) -> str:
    code, run_id, _ = cli("start", "--experiment", "churn", "--dataset-hash", "sha256:d", "--code-version", "git:c")
    assert code == 0 and run_id
    assert cli("log-param", run_id, "lr", "0.1")[0] == 0
    assert cli("log-metric", run_id, "acc", acc, "--step", "1")[0] == 0
    assert cli("end", run_id)[0] == 0
    return run_id


def test_cli_full_workflow_track_pick_best_register_promote_and_roll_back(cli):
    weak = finished_run(cli, "0.91")
    strong = finished_run(cli, "0.95")
    code, best, _ = cli("best", "--experiment", "churn", "--metric", "acc")
    assert (code, best) == (0, strong)
    assert cli("best", "--experiment", "churn", "--metric", "acc", "--mode", "min")[1] == weak

    assert cli("register", "--model", "churn", "--run", weak)[1] == "1"
    assert cli("register", "--model", "churn", "--run", strong)[1] == "2"
    for version in ("1", "2"):
        assert cli("validate", "--model", "churn", "--version", version)[0] == 0
        assert cli("promote", "--model", "churn", "--version", version, "--stage", "Staging")[0] == 0
    gate = ["--stage", "Production", "--metric", "acc", "--threshold", "0.9", "--min-improvement", "0.005"]
    assert cli("promote", "--model", "churn", "--version", "1", *gate)[0] == 0
    assert cli("promote", "--model", "churn", "--version", "2", *gate)[0] == 0

    code, listing, _ = cli("versions", "--model", "churn")
    assert code == 0
    assert listing.splitlines() == [f"1\tArchived\t{weak}", f"2\tProduction\t{strong}"]
    assert cli("rollback", "--model", "churn", "--reason", "bad release") == (0, "1", "")
    assert cli("versions", "--model", "churn")[1].splitlines()[0].split("\t")[1] == "Production"


def test_cli_reports_domain_errors_on_stderr_with_exit_code_1(cli):
    code, out, err = cli("log-metric", "no-such-run", "acc", "0.5")
    assert (code, out) == (1, "")
    assert err.startswith("error:") and "no-such-run" in err

    code, _, err = cli("best", "--experiment", "nothing", "--metric", "acc")
    assert code == 1 and "no finished run" in err

    run_id = finished_run(cli, "0.5")
    cli("register", "--model", "m", "--run", run_id)
    cli("promote", "--model", "m", "--version", "1", "--stage", "Staging")
    code, _, err = cli("promote", "--model", "m", "--version", "1", "--stage", "Production", "--metric", "acc", "--threshold", "0.9")
    assert code == 1 and "blocked" in err, "failed gates must be a non-zero exit so CI can stop the pipeline"
    assert cli("versions", "--model", "m")[1].split("\t")[1] == "Staging"


def test_cli_usage_errors_return_2_instead_of_raising(cli):
    assert cli()[0] == 2  # no command
    assert cli("frobnicate")[0] == 2
    assert cli("log-metric", "run-1", "acc", "not-a-number")[0] == 2
    assert cli("promote", "--model", "m", "--version", "1", "--stage", "Nonsense")[0] == 2
