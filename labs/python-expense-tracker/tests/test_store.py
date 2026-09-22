"""The JSON data file: loading, corrupt-file detection and atomic writes."""
import json
import os
from datetime import date
from pathlib import Path

import pytest

from lab import CorruptDataError, Expense, Store, load_store, resolve_path, save_store


def sample_store() -> Store:
    return Store(expenses=[Expense(1, 1250, "food", date(2025, 3, 1), "lunch"), Expense(4, 5, "bus", date(2025, 3, 2))],
                 budgets={"food": 30000, "bus": 5000}, next_id=5)


def test_loading_a_missing_file_gives_an_empty_store_and_does_not_create_it(data_file):
    store = load_store(data_file)
    assert store.expenses == [] and store.budgets == {} and store.next_id == 1
    assert not data_file.exists() and not data_file.parent.exists(), "reading must never create anything"


def test_save_then_load_round_trips_and_creates_missing_parent_directories(data_file):
    save_store(data_file, sample_store())
    assert load_store(data_file) == sample_store()
    raw = json.loads(data_file.read_text())
    assert all(type(e["amount_cents"]) is int for e in raw["expenses"]), "amounts are stored as integer cents"


def test_save_is_atomic_temp_file_in_same_directory_then_os_replace(data_file, monkeypatch):
    save_store(data_file, Store())
    calls = []
    real_replace = os.replace

    def spy(src, dst, *a, **kw):
        calls.append((Path(src), Path(dst), Path(src).exists()))
        return real_replace(src, dst, *a, **kw)

    monkeypatch.setattr(os, "replace", spy)
    save_store(data_file, sample_store())
    assert len(calls) == 1, "expected exactly one os.replace call"
    src, dst, existed = calls[0]
    assert dst == data_file and existed, "the finished temp file must exist when it is swapped in"
    assert src != data_file and src.parent == data_file.parent, "temp file must live next to the target (same filesystem)"
    assert sorted(p.name for p in data_file.parent.iterdir()) == [data_file.name], "no temp files left behind"


def test_a_failed_write_leaves_the_original_file_and_no_temp_litter(data_file, monkeypatch):
    save_store(data_file, Store())
    original = data_file.read_bytes()

    def boom(*a, **kw):
        raise OSError("disk exploded")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        save_store(data_file, sample_store())
    assert data_file.read_bytes() == original, "a crash during save must not corrupt the existing file"
    assert sorted(p.name for p in data_file.parent.iterdir()) == [data_file.name], "temp file must be cleaned up"


def test_truncated_json_raises_corrupt_data_error_and_the_file_is_untouched(data_file):
    save_store(data_file, sample_store())
    truncated = data_file.read_bytes()[:40]
    data_file.write_bytes(truncated)
    with pytest.raises(CorruptDataError) as info:
        load_store(data_file)
    assert info.value.exit_code == 4
    assert str(data_file) in str(info.value), "the message should name the broken file"
    assert data_file.read_bytes() == truncated


def test_structurally_invalid_files_are_corrupt(data_file):
    good = {"version": 1, "next_id": 2, "budgets": {"food": 100},
            "expenses": [{"id": 1, "amount_cents": 100, "category": "food", "date": "2025-03-01", "note": ""}]}

    def variant(**changes):
        expense_changes = changes.pop("expense", None)
        d = json.loads(json.dumps(good))
        d.update(changes)
        if expense_changes:
            d["expenses"][0].update(expense_changes)
        return d

    payloads = {
        "empty file": "",
        "top level is a list": [],
        "expenses missing": {"version": 1, "next_id": 1, "budgets": {}},
        "expenses not a list": variant(expenses={}),
        "amount is a float": variant(expense={"amount_cents": 12.5}),
        "amount is a bool": variant(expense={"amount_cents": True}),
        "amount not positive": variant(expense={"amount_cents": 0}),
        "date is impossible": variant(expense={"date": "2025-02-30"}),
        "category not a string": variant(expense={"category": 7}),
        "duplicate id": variant(expenses=[good["expenses"][0], good["expenses"][0]], next_id=3),
        "next_id not above ids": variant(next_id=1),
        "budget not positive": variant(budgets={"food": -1}),
    }
    for label, payload in payloads.items():
        text = payload if isinstance(payload, str) else json.dumps(payload)
        data_file.parent.mkdir(parents=True, exist_ok=True)
        data_file.write_text(text)
        with pytest.raises(CorruptDataError):
            load_store(data_file)
        assert data_file.read_text() == text, f"{label}: file must not be modified"
    data_file.write_text(json.dumps(good))
    assert load_store(data_file).expenses[0].amount_cents == 100, "the unmodified good payload must load"


def test_resolve_path_prefers_file_argument_then_env_then_home(tmp_path):
    assert resolve_path("/x/a.json", {"EXPENSE_FILE": "/y/b.json"}) == Path("/x/a.json")
    assert resolve_path(None, {"EXPENSE_FILE": "/y/b.json"}) == Path("/y/b.json")
    assert resolve_path(None, {}) == tmp_path / "home" / ".expenses.json", "default lives in the (test) home directory"
    assert resolve_path(None, {"EXPENSE_FILE": ""}) == tmp_path / "home" / ".expenses.json", "empty env var is unset"
