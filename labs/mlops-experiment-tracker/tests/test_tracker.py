"""Experiment tracker: runs, params, metrics, artifacts, comparison, best run."""

from __future__ import annotations

import hashlib
import math

import pytest

from lab import ImmutableParamError, RunNotFoundError, RunStateError, RunStatus, Tracker


def test_start_run_records_a_running_run_with_lineage_fields(tracker, clock):
    run_id = tracker.start_run("churn", name="baseline", dataset_hash="sha256:abc", code_version="git:1234")
    run = tracker.get_run(run_id)
    assert run.status is RunStatus.RUNNING and run.end_time is None
    assert (run.experiment, run.name) == ("churn", "baseline")
    assert (run.dataset_hash, run.code_version) == ("sha256:abc", "git:1234")
    assert run.start_time == clock.now
    assert run.params == {} and run.metrics == {} and run.tags == {} and run.artifacts == {}


def test_everything_is_persisted_in_sqlite_and_visible_to_a_new_tracker(db_path, tracker, tmp_path):
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"weights")
    run_id = tracker.start_run("exp", dataset_hash="d", code_version="c")
    tracker.log_param(run_id, "lr", 0.1)
    tracker.log_metric(run_id, "acc", 0.9, step=3)
    tracker.set_tag(run_id, "owner", "ana")
    tracker.log_artifact(run_id, artifact)
    tracker.end_run(run_id)

    with Tracker(db_path) as reopened:  # fresh connection, no shared Python state
        run = reopened.get_run(run_id)
    assert run.status is RunStatus.FINISHED and run.end_time is not None
    assert run.params == {"lr": "0.1"} and run.tags == {"owner": "ana"}
    assert run.metrics == {"acc": 0.9}
    assert run.artifacts == {"model.bin": hashlib.sha256(b"weights").hexdigest()}


def test_unknown_run_ids_raise_run_not_found(tracker):
    for call in (
        lambda: tracker.get_run("nope"),
        lambda: tracker.log_param("nope", "k", 1),
        lambda: tracker.log_metric("nope", "m", 1.0),
        lambda: tracker.end_run("nope"),
    ):
        with pytest.raises(RunNotFoundError):
            call()


def test_params_are_immutable_but_relogging_the_same_value_is_idempotent(tracker):
    run_id = tracker.start_run("exp")
    tracker.log_param(run_id, "lr", 0.01)
    tracker.log_param(run_id, "lr", 0.01)  # same value: fine
    tracker.log_param(run_id, "lr", "0.01")  # params are stored as strings, so this is the same value too
    with pytest.raises(ImmutableParamError):
        tracker.log_param(run_id, "lr", 0.02)
    assert tracker.get_run(run_id).params == {"lr": "0.01"}, "the original value must survive the rejected change"


def test_metric_history_keeps_every_step_final_is_the_highest_step_and_relogging_a_step_replaces_it(tracker):
    run_id = tracker.start_run("exp")
    for step, value in [(2, 0.8), (0, 0.5), (1, 0.7)]:  # deliberately out of order
        tracker.log_metric(run_id, "acc", value, step=step)
    assert tracker.metric_history(run_id, "acc") == [(0, 0.5), (1, 0.7), (2, 0.8)]
    tracker.log_metric(run_id, "acc", 0.4, step=1)  # a late write to an OLD step must not become "final"
    assert tracker.get_run(run_id).metrics["acc"] == 0.8

    tracker.log_metric(run_id, "loss", 1.0, step=5)
    tracker.log_metric(run_id, "loss", 0.5, step=5)  # same (key, step): replaced, not duplicated
    assert tracker.metric_history(run_id, "loss") == [(5, 0.5)]


def test_metrics_reject_nan_and_infinity_and_tags_can_be_overwritten(tracker):
    run_id = tracker.start_run("exp")
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            tracker.log_metric(run_id, "loss", bad)
    assert tracker.metric_history(run_id, "loss") == []
    tracker.set_tag(run_id, "stage", "draft")
    tracker.set_tag(run_id, "stage", "final")
    assert tracker.get_run(run_id).tags == {"stage": "final"}


def test_artifact_hash_is_the_real_sha256_even_for_files_larger_than_one_chunk(tracker, tmp_path):
    big = tmp_path / "big.bin"
    payload = (b"0123456789abcdef" * 1024) * 200 + b"tail"  # ~3.2 MB, not a multiple of the chunk size
    big.write_bytes(payload)
    run_id = tracker.start_run("exp")
    assert tracker.log_artifact(run_id, big) == hashlib.sha256(payload).hexdigest()
    same = tmp_path / "copy.bin"
    same.write_bytes(payload)
    assert tracker.log_artifact(run_id, same) == tracker.get_run(run_id).artifacts["big.bin"], "same bytes, same hash"
    assert set(tracker.get_run(run_id).artifacts) == {"big.bin", "copy.bin"}

    tracker.log_artifact(run_id, big)  # idempotent: no duplicate row, still one entry
    assert len(tracker.get_run(run_id).artifacts) == 2


def test_missing_artifact_file_raises_and_records_nothing(tracker, tmp_path):
    run_id = tracker.start_run("exp")
    with pytest.raises(FileNotFoundError):
        tracker.log_artifact(run_id, tmp_path / "ghost.bin")
    assert tracker.get_run(run_id).artifacts == {}


def test_a_finished_run_is_frozen_and_cannot_end_twice(tracker, tmp_path):
    artifact = tmp_path / "a.txt"
    artifact.write_text("x")
    run_id = tracker.start_run("exp")
    tracker.end_run(run_id)
    frozen_calls = {
        "log_param": lambda: tracker.log_param(run_id, "k", "v"),
        "log_metric": lambda: tracker.log_metric(run_id, "m", 1.0),
        "set_tag": lambda: tracker.set_tag(run_id, "k", "v"),
        "log_artifact": lambda: tracker.log_artifact(run_id, artifact),
        "end_run": lambda: tracker.end_run(run_id),
    }
    for name, call in frozen_calls.items():
        with pytest.raises(RunStateError):
            call()
            pytest.fail(f"{name} on a finished run should raise RunStateError")

    failed = tracker.start_run("exp")
    tracker.end_run(failed, "FAILED")
    assert tracker.get_run(failed).status is RunStatus.FAILED
    with pytest.raises(RunStateError):
        tracker.log_param(failed, "k", "v")


def test_experiment_names_with_sql_metacharacters_are_stored_verbatim(tracker):
    nasty = "x'; DROP TABLE runs; --"
    run_id = tracker.start_run(nasty)
    assert tracker.get_run(run_id).experiment == nasty
    assert tracker.list_runs(nasty) == [run_id]
    assert tracker.list_runs("x") == []


def test_compare_runs_builds_a_metric_table_and_reports_only_params_that_differ(tracker, make_run):
    a = make_run(metrics={"acc": 0.90, "f1": 0.80}, params={"lr": 0.1, "epochs": 10, "seed": 42})
    b = make_run(metrics={"acc": 0.93}, params={"lr": 0.01, "epochs": 10, "seed": 42, "dropout": 0.3})

    result = tracker.compare_runs([a, b])
    assert result.metrics == {a: {"acc": 0.90, "f1": 0.80}, b: {"acc": 0.93, "f1": None}}
    assert result.differing_params == {
        "lr": {a: "0.1", b: "0.01"},
        "dropout": {a: None, b: "0.3"},
    }, "epochs and seed are identical in both runs and must not appear"
    assert tracker.compare_runs([a, b], metrics=["acc"]).metrics[b] == {"acc": 0.93}


def test_best_run_supports_max_and_min_uses_final_step_and_skips_unfinished_or_metricless_runs(tracker, make_run):
    low = make_run(metrics={"acc": 0.70, "loss": 0.9})
    high = make_run(metrics={"acc": 0.95, "loss": 0.2})
    make_run(metrics={"acc": 0.99}, finish=False)  # still RUNNING: must be ignored
    failed = make_run(metrics={"acc": 0.999}, finish=False)
    tracker.end_run(failed, "FAILED")  # FAILED: must be ignored
    make_run(metrics={"f1": 1.0})  # never logged acc
    make_run("other-experiment", metrics={"acc": 1.0})

    assert tracker.best_run("exp", "acc") == high
    assert tracker.best_run("exp", "loss", mode="min") == high
    assert tracker.best_run("exp", "acc", mode="min") == low

    assert tracker.best_run("empty-experiment", "acc") is None

    # "final" means the highest STEP, not the best step: 0.99 at step 0 then 0.60 at step 1 is a 0.60 run
    dropper = tracker.start_run("exp-steps")
    tracker.log_metric(dropper, "acc", 0.99, step=0)
    tracker.log_metric(dropper, "acc", 0.60, step=1)
    tracker.end_run(dropper)
    steady = tracker.start_run("exp-steps")
    tracker.log_metric(steady, "acc", 0.80, step=0)
    tracker.end_run(steady)
    assert tracker.best_run("exp-steps", "acc") == steady


def test_best_run_ties_are_broken_deterministically_by_start_time_then_run_id(tracker, clock):
    first = tracker.start_run("exp")  # run-001 at t0
    clock.advance(10)
    second = tracker.start_run("exp")  # run-002 at t0+10
    third = tracker.start_run("exp")  # run-003, the very same instant as run-002
    for run_id in (third, second, first):  # finish in a scrambled order: finishing order must not matter
        tracker.log_metric(run_id, "acc", 0.9)
        tracker.end_run(run_id)
    assert tracker.best_run("exp", "acc") == first, "earliest start wins the tie"
    assert tracker.best_run("exp", "acc", mode="min") == first, "and min mode breaks ties the same way"

    clock.advance(10)
    twin_a = tracker.start_run("exp2")  # run-004
    twin_b = tracker.start_run("exp2")  # run-005, identical start time
    tracker.log_metric(twin_b, "acc", 0.5)
    tracker.log_metric(twin_a, "acc", 0.5 + 1e-15)  # float noise, not a real difference
    tracker.end_run(twin_b)
    tracker.end_run(twin_a)
    assert tracker.best_run("exp2", "acc") == twin_a, "equal start time: the lowest run_id wins"
