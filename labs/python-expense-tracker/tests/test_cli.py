"""End-to-end behaviour through ``main(argv)`` (plus one real subprocess run)."""
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from conftest import TARGET_DIR

from lab import main

FIXED_TODAY = lambda: date(2025, 3, 15)  # noqa: E731


def run(capsys, *argv, env=None):
    code = main([str(a) for a in argv], today=FIXED_TODAY, environ=env if env is not None else os.environ)
    out, err = capsys.readouterr()
    return code, out, err


def add(capsys, f, amount, category="food", day="2025-03-01", *extra):
    code, out, err = run(capsys, "--file", f, "add", "--amount", amount, "--category", category, "--date", day, *extra)
    assert code == 0, f"add {amount} {category} failed: {err}"
    return out.strip()


def rows(out):
    return [line.split() for line in out.splitlines()]


def test_add_prints_the_id_stores_integer_cents_and_gives_distinct_ids(capsys, data_file):
    first = add(capsys, data_file, "12.50")
    second = add(capsys, data_file, "0.10")  # same instant, different record
    assert (first, second) == ("1", "2")
    stored = json.loads(data_file.read_text())
    assert [e["amount_cents"] for e in stored["expenses"]] == [1250, 10]
    assert all(type(e["amount_cents"]) is int for e in stored["expenses"])


def test_add_defaults_the_date_to_today_and_keeps_the_note(capsys, data_file):
    code, out, _ = run(capsys, "--file", data_file, "add", "--amount", "4", "--category", "Coffee", "--note", "flat white")
    assert code == 0
    code, out, _ = run(capsys, "--file", data_file, "list", "--json")
    (item,) = json.loads(out)
    assert (item["date"], item["category"], item["note"]) == ("2025-03-15", "coffee", "flat white")


def test_invalid_input_exits_2_with_a_message_and_writes_nothing(capsys, data_file):
    bad_argvs = [["--amount", "-5", "--category", "food"], ["--amount", "0", "--category", "food"],
                 ["--amount", "abc", "--category", "food"], ["--amount", "1.234", "--category", "food"],
                 ["--amount", "5", "--category", "food", "--date", "2025-02-30"],
                 ["--amount", "5", "--category", "food", "--date", "2025-13-01"],
                 ["--amount", "5", "--category", "bad name"]]
    for argv in bad_argvs:  # 1) no file yet: it must not be created
        code, out, err = run(capsys, "--file", data_file, "add", *argv)
        assert code == 2, f"{argv} should be rejected with exit code 2, got {code}"
        assert out == "" and "error" in err.lower(), "results go to stdout, errors to stderr"
        assert not data_file.exists(), f"{argv}: a rejected add must not create the file"
    add(capsys, data_file, "1.00")  # 2) existing file: byte-for-byte unchanged
    before = data_file.read_bytes()
    for argv in bad_argvs:
        assert run(capsys, "--file", data_file, "add", *argv)[0] == 2
        assert data_file.read_bytes() == before, f"{argv}: partial write detected"


def test_add_rejects_a_category_without_a_budget_once_any_budget_exists(capsys, data_file):
    assert run(capsys, "--file", data_file, "budget", "set", "food", "300")[0] == 0
    before = data_file.read_bytes()
    code, out, err = run(capsys, "--file", data_file, "add", "--amount", "5", "--category", "travel", "--date", "2025-03-01")
    assert (code, out) == (2, "") and "travel" in err
    assert data_file.read_bytes() == before
    add(capsys, data_file, "5", "food")


def test_list_on_an_empty_store_exits_0_with_just_the_header(capsys, data_file):
    code, out, err = run(capsys, "--file", data_file, "list")
    assert code == 0 and err == ""
    lines = rows(out)
    assert len(lines) == 1 and lines[0] == ["ID", "DATE", "CATEGORY", "AMOUNT", "NOTE"]
    assert not data_file.exists()


def test_list_prints_a_sorted_table_and_supports_category_since_until_filters(capsys, data_file):
    add(capsys, data_file, "3.00", "food", "2025-03-05")
    add(capsys, data_file, "1.50", "bus", "2025-03-01")
    add(capsys, data_file, "2.25", "food", "2025-03-01", "--note", "eggs and milk")
    add(capsys, data_file, "9.00", "food", "2025-04-01")
    _, out, _ = run(capsys, "--file", data_file, "list")
    body = rows(out)[1:]
    assert [r[:4] for r in body] == [["2", "2025-03-01", "bus", "1.50"], ["3", "2025-03-01", "food", "2.25"],
                                     ["1", "2025-03-05", "food", "3.00"], ["4", "2025-04-01", "food", "9.00"]], (
        "rows are sorted by date then id")
    assert body[1][4:] == ["eggs", "and", "milk"]
    assert out == run(capsys, "--file", data_file, "list")[1], "output must be stable between runs"
    ids = lambda *a: [r[0] for r in rows(run(capsys, "--file", data_file, "list", *a)[1])[1:]]  # noqa: E731
    assert ids("--category", "FOOD") == ["3", "1", "4"]
    assert ids("--since", "2025-03-05") == ["1", "4"]
    assert ids("--until", "2025-03-01") == ["2", "3"]
    assert ids("--category", "food", "--since", "2025-03-02", "--until", "2025-03-31") == ["1"]
    assert run(capsys, "--file", data_file, "list", "--since", "2025-02-30")[0] == 2


def test_list_json_is_machine_readable_and_empty_store_gives_an_empty_array(capsys, data_file):
    code, out, _ = run(capsys, "--file", data_file, "list", "--json")
    assert (code, json.loads(out)) == (0, [])
    add(capsys, data_file, "12.50", "food", "2025-03-01", "--note", "lunch")
    code, out, _ = run(capsys, "--file", data_file, "list", "--json")
    assert code == 0
    assert json.loads(out) == [{"id": 1, "date": "2025-03-01", "category": "food", "amount": "12.50",
                                "amount_cents": 1250, "note": "lunch"}]


def test_report_totals_per_category_and_grand_total_equal_the_sum_of_rows(capsys, data_file):
    add(capsys, data_file, "0.10", "food", "2025-03-01")
    add(capsys, data_file, "0.20", "food", "2025-03-31")
    add(capsys, data_file, "5.00", "bus", "2025-03-10")
    add(capsys, data_file, "99.00", "food", "2025-04-01")
    code, out, err = run(capsys, "--file", data_file, "report", "--month", "2025-03")
    assert (code, err) == (0, "")
    table = [(r[0], r[1]) for r in rows(out)]
    assert table == [("bus", "5.00"), ("food", "0.30"), ("TOTAL", "5.30")], "0.10 + 0.20 must be exactly 0.30"
    code, out, _ = run(capsys, "--file", data_file, "report", "--month", "2025-03", "--json")
    data = json.loads(out)
    assert data["categories"] == {"bus": "5.00", "food": "0.30"} and data["total"] == "5.30" and data["total_cents"] == 530


def test_report_for_an_empty_month_is_zero_and_a_malformed_month_is_a_usage_error(capsys, data_file):
    add(capsys, data_file, "5.00", "food", "2025-03-01")
    code, out, _ = run(capsys, "--file", data_file, "report", "--month", "2025-05")
    assert code == 0 and [(r[0], r[1]) for r in rows(out)] == [("TOTAL", "0.00")]
    for bad in ("2025-13", "2025", "March"):
        code, out, err = run(capsys, "--file", data_file, "report", "--month", bad)
        assert (code, out) == (2, "") and err, f"--month {bad!r} should be rejected"


def test_remove_deletes_by_id_and_unknown_id_exits_3(capsys, data_file):
    add(capsys, data_file, "1.00")
    add(capsys, data_file, "2.00")
    code, out, _ = run(capsys, "--file", data_file, "remove", "1")
    assert (code, out.split()) == (0, ["removed", "1"])
    assert [r[0] for r in rows(run(capsys, "--file", data_file, "list")[1])[1:]] == ["2"]
    before = data_file.read_bytes()
    code, out, err = run(capsys, "--file", data_file, "remove", "99")
    assert (code, out) == (3, "") and "99" in err, "not found -> exit 3, message on stderr"
    assert data_file.read_bytes() == before
    assert run(capsys, "--file", data_file, "remove", "abc")[0] == 2


def test_a_corrupt_data_file_exits_4_for_every_command_and_is_left_untouched(capsys, data_file):
    data_file.parent.mkdir(parents=True)
    add(capsys, data_file, "1.00")
    truncated = data_file.read_bytes()[:30]
    data_file.write_bytes(truncated)
    commands = [["list"], ["list", "--json"], ["report", "--month", "2025-03"], ["remove", "1"],
                ["budget", "set", "food", "10"], ["budget", "list"],
                ["add", "--amount", "1", "--category", "food", "--date", "2025-03-01"]]
    for cmd in commands:
        code, out, err = run(capsys, "--file", data_file, *cmd)
        assert code == 4, f"{cmd}: expected exit code 4 for a corrupt file, got {code}"
        assert out == "" and str(data_file) in err, f"{cmd}: nothing on stdout, the file named on stderr"
        assert data_file.read_bytes() == truncated, f"{cmd}: a corrupt file must be left untouched"


def test_file_option_beats_env_var_and_is_accepted_before_or_after_the_subcommand(capsys, tmp_path):
    env_file, opt_file = tmp_path / "env.json", tmp_path / "opt.json"
    env = {"EXPENSE_FILE": str(env_file)}
    assert run(capsys, "add", "--amount", "1", "--category", "a", "--date", "2025-03-01", env=env)[0] == 0
    assert env_file.exists() and not opt_file.exists(), "EXPENSE_FILE is used when --file is absent"
    assert run(capsys, "--file", opt_file, "add", "--amount", "2", "--category", "b", "--date", "2025-03-01", env=env)[0] == 0
    assert run(capsys, "add", "--file", opt_file, "--amount", "3", "--category", "c", "--date", "2025-03-01", env=env)[0] == 0
    assert [e["category"] for e in json.loads(opt_file.read_text())["expenses"]] == ["b", "c"]
    assert [e["category"] for e in json.loads(env_file.read_text())["expenses"]] == ["a"]


def test_budget_set_and_list_and_an_over_budget_add_warns_on_stderr_but_still_succeeds(capsys, data_file):
    code, out, _ = run(capsys, "--file", data_file, "budget", "set", "Food", "300")
    assert (code, out.split()) == (0, ["budget", "food", "300.00"])
    assert run(capsys, "--file", data_file, "budget", "set", "bus", "20.50")[0] == 0
    assert [r for r in rows(run(capsys, "--file", data_file, "budget", "list")[1])] == [["bus", "20.50"], ["food", "300.00"]]
    code, out, err = run(capsys, "--file", data_file, "add", "--amount", "250", "--category", "food", "--date", "2025-03-02")
    assert (code, out.strip(), err) == (0, "1", ""), "under budget: no warning"
    code, out, err = run(capsys, "--file", data_file, "add", "--amount", "70.50", "--category", "food", "--date", "2025-03-09")
    assert (code, out.strip()) == (0, "2"), "over budget is a warning, not a failure, and the record is saved"
    assert "over budget" in err and "food" in err and "2025-03" in err and "320.50" in err and "300.00" in err
    assert len(json.loads(data_file.read_text())["expenses"]) == 2
    code, out, err = run(capsys, "--file", data_file, "add", "--amount", "300", "--category", "food", "--date", "2025-04-02")
    assert (code, err) == (0, ""), "budgets are per month: April is a fresh month"


def test_spending_exactly_the_budget_is_not_a_warning_and_report_warns_for_exceeded_months(capsys, data_file):
    run(capsys, "--file", data_file, "budget", "set", "food", "10")
    _, _, err = run(capsys, "--file", data_file, "add", "--amount", "10", "--category", "food", "--date", "2025-03-01")
    assert err == "", "exactly at the limit is fine"
    code, out, err = run(capsys, "--file", data_file, "report", "--month", "2025-03")
    assert (code, err) == (0, "")
    run(capsys, "--file", data_file, "add", "--amount", "0.01", "--category", "food", "--date", "2025-03-02")
    code, out, err = run(capsys, "--file", data_file, "report", "--month", "2025-03")
    assert code == 0 and "over budget" in err and "10.01" in err, "report also warns, on stderr"
    assert "over budget" not in out and rows(out)[-1][:2] == ["TOTAL", "10.01"], "stdout stays machine-clean"


def test_usage_errors_exit_2_and_help_exits_0_without_raising(capsys, data_file):
    for argv in ([], ["bogus"], ["add"], ["add", "--amount", "5"], ["list", "--nope"], ["budget"], ["budget", "set", "food"]):
        assert run(capsys, *argv)[0] == 2, f"{argv} is a usage error"
    code, out, _ = run(capsys, "--help")
    assert code == 0 and "add" in out and "report" in out


def test_console_behaviour_end_to_end_in_a_real_subprocess(tmp_path):
    data = tmp_path / "e.json"
    env = {**os.environ, "PYTHONPATH": str(TARGET_DIR), "EXPENSE_FILE": str(data), "HOME": str(tmp_path),
           "PYTHONDONTWRITEBYTECODE": "1"}

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "lab", *args], capture_output=True, text=True, env=env,
                              cwd=tmp_path, timeout=30)

    r = cli("add", "--amount", "12.50", "--category", "food", "--date", "2025-03-01")
    assert (r.returncode, r.stdout, r.stderr) == (0, "1\n", ""), r
    r = cli("report", "--month", "2025-03")
    assert r.returncode == 0 and r.stdout.split()[-2:] == ["TOTAL", "12.50"], r
    r = cli("remove", "42")
    assert (r.returncode, r.stdout) == (3, "") and r.stderr, r
    r = cli("add", "--amount", "-1", "--category", "food")
    assert r.returncode == 2 and r.stdout == "", r
    data.write_text("{not json")
    r = cli("list")
    assert (r.returncode, r.stdout) == (4, "") and r.stderr, r
