"""Command line: output formats and exit codes."""

from __future__ import annotations

import io
import json
from pathlib import Path

from helpers import FIXTURES
from lab.cli import main


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(list(argv), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_clean_file_exits_0_and_bad_file_exits_1() -> None:
    code, out, _ = run(str(FIXTURES / "compose_good.yml"))
    assert code == 0 and out == "No findings in 1 file(s)\n"
    code, out, _ = run(str(FIXTURES / "compose_bad.yml"))
    assert code == 1
    assert "no-privileged" in out and "compose_bad.yml:6:" in out


def test_fail_on_threshold_controls_the_exit_code(tmp_path: Path) -> None:
    f = tmp_path / "m.yml"
    f.write_text("services:\n  web:\n    image: a:latest\n    mem_limit: 1m\n    healthcheck: {test: [CMD, 'true']}\n")
    assert run(str(f))[0] == 0, "default --fail-on is high; a medium finding passes"
    assert run(str(f), "--fail-on", "medium")[0] == 1
    assert run(str(f), "--fail-on", "critical")[0] == 0
    assert run(str(FIXTURES / "compose_bad.yml"), "--fail-on", "critical")[0] == 1


def test_json_format_is_valid_json() -> None:
    code, out, _ = run(str(FIXTURES / "k8s_bad.yaml"), "--format", "json")
    assert code == 1
    assert json.loads(out)["summary"]["findings"] == 9


def test_multiple_paths_and_directories() -> None:
    code, out, _ = run(str(FIXTURES), "--format", "json")
    data = json.loads(out)
    assert data["summary"]["files"] == 5 and code == 1
    assert {Path(f["file"]).name for f in data["findings"]} == {"compose_bad.yml", "k8s_bad.yaml", "compose_anchors.yml"}


def test_config_file_disables_rules_and_bad_config_exits_2(tmp_path: Path) -> None:
    cfg = tmp_path / ".auditor.yaml"
    cfg.write_text("rules:\n  no-privileged: {enabled: false}\n  no-plaintext-secrets: {enabled: false}\n")
    code, out, _ = run(str(FIXTURES / "compose_bad.yml"), "--config", str(cfg))
    assert "no-privileged" not in out and "no-plaintext-secrets" not in out
    cfg.write_text("rules:\n  not-a-rule: {enabled: false}\n")
    code, out, err = run(str(FIXTURES / "compose_bad.yml"), "--config", str(cfg))
    assert code == 2 and out == "" and "not-a-rule" in err
    assert run(str(FIXTURES / "compose_bad.yml"), "--config", str(tmp_path / "missing.yaml"))[0] == 2


def test_missing_file_and_invalid_yaml_exit_2(tmp_path: Path) -> None:
    code, out, _ = run(str(tmp_path / "nope.yml"))
    assert code == 2 and "nope.yml" in out
    bad = tmp_path / "bad.yml"
    bad.write_text("a: [1\n")
    code, out, _ = run(str(bad), str(FIXTURES / "compose_bad.yml"))
    assert code == 2 and "error:" in out and "no-privileged" in out, "errors must not hide findings from other files"


def test_usage_errors_exit_2() -> None:
    assert run()[0] == 2
    assert run("x.yml", "--fail-on", "urgent")[0] == 2
