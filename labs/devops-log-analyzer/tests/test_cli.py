import io
import json

import pytest
from helpers import at, make_line

from lab import main


def write_log(tmp_path, lines, name="access.log"):
    p = tmp_path / name
    p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return str(p)


@pytest.fixture
def sample_log(tmp_path):
    lines = [make_line(ip="1.1.1.1", path="/home", status=200, rt=0.1, when=at(i)) for i in range(8)]
    lines += [make_line(ip="2.2.2.2", path="/api", status=500, rt=1.0, when=at(10)),
              make_line(ip="2.2.2.2", path="/api", status=200, rt=0.3, when=at(11))]
    return write_log(tmp_path, lines)


def test_text_report_mentions_the_key_numbers(sample_log, capsys):
    assert main([sample_log]) == 0
    out = capsys.readouterr().out
    assert "1.1.1.1" in out and "/api" in out
    assert "10" in out, "parsed line count should be shown"
    assert "10.00%" in out, "overall 5xx rate (1 of 10) should be shown as a percentage"


def test_json_format_is_valid_and_has_stable_keys(sample_log, capsys):
    assert main(["--format", "json", sample_log]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["parsed"] == 10 and data["skipped"] == 0
    assert data["error_rate"] == pytest.approx(0.1)
    assert data["top_ips"][0] == {"ip": "1.1.1.1", "count": 8}
    assert set(data["latency"]) == {"p50", "p95", "p99"}
    assert data["hourly"][0]["hour"] == "2024-03-10T13"
    assert data["suspicious"] == []


def test_fail_on_error_rate_exceeded_returns_1(sample_log, capsys):
    assert main([sample_log, "--fail-on-error-rate", "0.05"]) == 1
    assert "exceeds" in capsys.readouterr().err.lower()


def test_fail_on_error_rate_equal_to_limit_passes(sample_log):
    assert main([sample_log, "--fail-on-error-rate", "0.1"]) == 0, "gate is strictly greater-than"


def test_fail_on_error_rate_not_exceeded_or_not_requested_returns_0(sample_log, tmp_path):
    assert main([sample_log, "--fail-on-error-rate", "0.5"]) == 0
    all_5xx = write_log(tmp_path, [make_line(status=500)] * 5, name="bad.log")
    assert main([all_5xx]) == 0, "without the flag, errors never change the exit code"


def test_empty_file_is_ok_and_reports_zero(tmp_path, capsys):
    path = write_log(tmp_path, [])
    assert main(["--format", "json", path, "--fail-on-error-rate", "0"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["parsed"] == 0 and data["error_rate"] == 0


def test_all_malformed_file_exits_2_with_message(tmp_path, capsys):
    path = write_log(tmp_path, ["nope", "still nope", "<html>"])
    assert main([path]) == 2, "a file with zero valid lines is the wrong input, not a healthy site"
    assert "3" in capsys.readouterr().err


def test_mixed_malformed_lines_are_tolerated_and_reported(tmp_path, capsys):
    path = write_log(tmp_path, [make_line(), "oops", make_line(), "", "also bad"])
    assert main(["--format", "json", path]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)  # stdout must stay pure JSON: diagnostics belong on stderr
    assert (data["parsed"], data["skipped"]) == (2, 2)


def test_binary_junk_does_not_crash_the_reader(tmp_path, capsys):
    p = tmp_path / "bin.log"
    p.write_bytes(make_line().encode() + b"\n\xff\xfe\x00\x81garbage\n" + make_line().encode() + b"\n")
    assert main(["--format", "json", str(p)]) == 0
    assert json.loads(capsys.readouterr().out)["skipped"] == 1


def test_missing_file_and_bad_arguments_return_2_instead_of_raising(tmp_path, capsys, sample_log):
    assert main([str(tmp_path / "nope.log")]) == 2
    assert "nope.log" in capsys.readouterr().err
    assert main([sample_log, "--format", "xml"]) == 2
    assert main([]) == 2
    assert main([sample_log, "--top", "0"]) == 2


def test_reads_from_stdin_with_dash(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(make_line(ip="4.4.4.4") + "\n"))
    assert main(["-", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["top_ips"][0]["ip"] == "4.4.4.4"


def test_bruteforce_flags_are_wired_through_the_cli(tmp_path, capsys):
    lines = [make_line(ip="6.6.6.6", status=401, when=at(i * 10)) for i in range(4)]
    path = write_log(tmp_path, lines)
    assert main(["--format", "json", path, "--bf-threshold", "4", "--bf-window", "60"]) == 0
    assert [s["ip"] for s in json.loads(capsys.readouterr().out)["suspicious"]] == ["6.6.6.6"]
    # 30 s span, window 30 s -> edge is exclusive -> not suspicious
    assert main(["--format", "json", path, "--bf-threshold", "4", "--bf-window", "30"]) == 0
    assert json.loads(capsys.readouterr().out)["suspicious"] == []


def test_cli_streams_the_file_line_by_line(tmp_path, monkeypatch):
    """The file object must be iterated lazily (not .read()/.readlines())."""
    path = write_log(tmp_path, [make_line(when=at(i)) for i in range(50)])
    import builtins
    real_open = builtins.open
    calls = []

    class Spy:
        def __init__(self, fh):
            self._fh = fh

        def __iter__(self):
            return iter(self._fh)

        def __enter__(self):
            self._fh.__enter__()
            return self

        def __exit__(self, *a):
            return self._fh.__exit__(*a)

        def __getattr__(self, name):
            if name in {"read", "readlines"}:
                calls.append(name)
            return getattr(self._fh, name)

    def spy_open(file, *a, **k):
        fh = real_open(file, *a, **k)
        return Spy(fh) if str(file) == path else fh

    monkeypatch.setattr(builtins, "open", spy_open)
    assert main([path]) == 0
    assert calls == [], f"whole-file reads detected: {calls}; iterate the file object instead"
