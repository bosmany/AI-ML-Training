"""Pure domain logic: money, dates, validation, ledger functions. No files, no argparse."""
from datetime import date

import pytest

from lab import (Expense, NotFoundError, Store, ValidationError, add_expense, budget_warnings, filter_expenses,
                 format_cents, month_totals, normalize_category, parse_amount, parse_date, parse_month,
                 remove_expense, set_budget)


def test_parse_amount_returns_integer_cents_without_float_drift():
    cases = {"12.50": 1250, "12": 1200, "0.1": 10, "0.01": 1, "0.20": 20, " 3.05 ": 305, "1234567.89": 123456789}
    for text, cents in cases.items():
        got = parse_amount(text)
        assert got == cents and type(got) is int, f"parse_amount({text!r}) should be the int {cents}, got {got!r}"


def test_parse_amount_rejects_bad_input_with_a_validation_error():
    for bad in ["", "abc", "-5", "-0.01", "0", "0.00", "12.345", "1e2", "nan", "inf", "1,50", "12.", ".5", "1 2"]:
        with pytest.raises(ValidationError) as info:
            parse_amount(bad)
        assert info.value.exit_code == 2, "rejected input maps to the usage exit code 2"
        assert str(info.value), f"the error for {bad!r} needs a human-readable message"


def test_format_cents_always_shows_two_decimals():
    assert [format_cents(c) for c in (0, 5, 50, 100, 1250, 123456789)] == [
        "0.00", "0.05", "0.50", "1.00", "12.50", "1234567.89"]


def test_parse_date_and_month_accept_real_values_and_reject_impossible_ones():
    assert parse_date("2025-03-01") == date(2025, 3, 1)
    assert parse_date("2024-02-29") == date(2024, 2, 29), "2024 is a leap year"
    assert parse_month("2025-03") == (2025, 3)
    for bad in ["2025-02-30", "2025-13-01", "2023-02-29", "2025-00-10", "20250301", "2025-3-1", "", "yesterday"]:
        with pytest.raises(ValidationError):
            parse_date(bad)
    for bad in ["2025-13", "2025-00", "2025-3", "2025", "03-2025", ""]:
        with pytest.raises(ValidationError):
            parse_month(bad)


def test_normalize_category_lowercases_and_rejects_bad_names():
    assert normalize_category("  Food ") == "food"
    assert normalize_category("eating-out_2") == "eating-out_2"
    for bad in ["", "   ", "two words", "a/b", "café"]:
        with pytest.raises(ValidationError):
            normalize_category(bad)


def test_add_expense_assigns_increasing_ids_that_are_never_reused():
    store = Store()
    a = add_expense(store, amount_cents=100, category="Food", day=date(2025, 3, 1))
    b = add_expense(store, amount_cents=200, category=" food ", day=date(2025, 3, 1), note=" lunch ")
    assert (a.id, b.id) == (1, 2)
    assert (b.category, b.note) == ("food", "lunch"), "category is normalized and note stripped"
    remove_expense(store, 2)
    c = add_expense(store, amount_cents=300, category="food", day=date(2025, 3, 1))
    assert c.id == 3, "ids come from a counter; a removed id must not be handed out again"
    assert [e.id for e in store.expenses] == [1, 3]


def test_add_expense_rejects_unknown_category_when_budgets_exist_and_changes_nothing():
    store = Store()
    add_expense(store, amount_cents=100, category="anything", day=date(2025, 3, 1))  # no budgets yet: fine
    set_budget(store, "food", 30000)
    before = (list(store.expenses), dict(store.budgets), store.next_id)
    with pytest.raises(ValidationError, match="travel"):
        add_expense(store, amount_cents=500, category="travel", day=date(2025, 3, 2))
    with pytest.raises(ValidationError):
        add_expense(store, amount_cents=0, category="food", day=date(2025, 3, 2))
    assert (store.expenses, store.budgets, store.next_id) == before, "a rejected add must not partially modify the store"
    add_expense(store, amount_cents=500, category="FOOD", day=date(2025, 3, 2))  # a budgeted category is accepted


def test_filter_expenses_is_inclusive_and_sorted_by_date_then_id():
    exps = [Expense(1, 100, "food", date(2025, 3, 5)), Expense(2, 100, "fun", date(2025, 3, 1)),
            Expense(3, 100, "food", date(2025, 3, 1)), Expense(4, 100, "food", date(2025, 4, 1))]
    assert [e.id for e in filter_expenses(exps)] == [2, 3, 1, 4]
    assert [e.id for e in filter_expenses(exps, category="Food")] == [3, 1, 4]
    assert [e.id for e in filter_expenses(exps, since=date(2025, 3, 5), until=date(2025, 4, 1))] == [1, 4]
    assert [e.id for e in filter_expenses(exps, until=date(2025, 3, 1))] == [2, 3], "until is inclusive"
    assert filter_expenses([]) == []
    assert filter_expenses(exps, category="nope") == []


def test_month_totals_are_exact_sorted_and_scoped_to_the_month():
    exps = [Expense(1, 10, "food", date(2025, 3, 1)), Expense(2, 20, "food", date(2025, 3, 31)),
            Expense(3, 500, "bus", date(2025, 3, 15)), Expense(4, 999, "food", date(2025, 2, 28)),
            Expense(5, 999, "food", date(2025, 4, 1)), Expense(6, 7, "food", date(2024, 3, 10))]
    totals = month_totals(exps, (2025, 3))
    assert totals == {"bus": 500, "food": 30}, "0.10 + 0.20 must be exactly 0.30, other months excluded"
    assert list(totals) == ["bus", "food"], "keys sorted alphabetically"
    assert month_totals(exps, (2025, 5)) == {}


def test_remove_expense_returns_it_and_raises_not_found_for_unknown_ids():
    store = Store()
    e = add_expense(store, amount_cents=100, category="food", day=date(2025, 3, 1))
    with pytest.raises(NotFoundError) as info:
        remove_expense(store, 99)
    assert info.value.exit_code == 3
    assert remove_expense(store, e.id) == e
    assert store.expenses == []


def test_set_budget_validates_and_overwrites():
    store = Store()
    set_budget(store, " Food ", 30000)
    set_budget(store, "food", 25000)
    assert store.budgets == {"food": 25000}
    for bad in (0, -5):
        with pytest.raises(ValidationError):
            set_budget(store, "food", bad)
    with pytest.raises(ValidationError):
        set_budget(store, "bad name", 100)


def test_budget_warnings_fire_only_when_strictly_exceeded_in_that_month():
    store = Store()
    set_budget(store, "food", 3000)
    set_budget(store, "bus", 1000)
    set_budget(store, "fun", 500)
    for amount, cat, day in [(3000, "food", date(2025, 3, 1)), (600, "bus", date(2025, 3, 2)),
                             (401, "bus", date(2025, 3, 3)), (9999, "fun", date(2025, 4, 1))]:
        add_expense(store, amount_cents=amount, category=cat, day=day)
    warnings = budget_warnings(store, (2025, 3))
    assert [(w.category, w.spent_cents, w.limit_cents) for w in warnings] == [("bus", 1001, 1000)], (
        "food is exactly at its limit (no warning) and fun's overspend is in another month")
    assert [w.category for w in budget_warnings(store, (2025, 4))] == ["fun"]
