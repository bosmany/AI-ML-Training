"""Model registry: versions, stages, promotion gates, rollback, lineage."""

from __future__ import annotations

import pytest

from lab import (
    InvalidTransitionError,
    LineageError,
    ModelVersionNotFoundError,
    PromotionBlockedError,
    PromotionPolicy,
    Registry,
    RegistryError,
    RollbackError,
    Stage,
    at_least,
    meets_margin,
)

POLICY = PromotionPolicy(metric="acc", threshold=0.90, min_improvement=0.005)


@pytest.fixture
def stage_version(registry, make_run):
    """Register a run with the given metric and move it to Staging (validated by default)."""

    def _stage(acc: float, *, validated: bool = True, model: str = "churn", extra: dict | None = None) -> int:
        run_id = make_run(metrics={"acc": acc, **(extra or {})})
        version = registry.register_version(model, run_id)
        if validated:
            registry.mark_validated(model, version)
        registry.transition(model, version, Stage.STAGING)
        return version

    return _stage


# ------------------------------------------------------------------ float-safe helpers
def test_margin_and_threshold_helpers_are_float_safe():
    assert 0.938 - 0.933 < 0.005, "sanity: the naive comparison is False (0.004999999999999893)"
    assert meets_margin(0.938, 0.933, 0.005) is True
    assert meets_margin(0.937, 0.933, 0.005) is False
    assert meets_margin(0.500, 0.500, 0.0) is True, "a zero margin accepts an equal score"
    assert meets_margin(0.20, 0.30, 0.05, higher_is_better=False) is True
    assert meets_margin(0.28, 0.30, 0.05, higher_is_better=False) is False
    assert at_least(0.1 + 0.2, 0.3) is True, "0.1 + 0.2 is 0.30000000000000004"
    assert at_least(0.9, 0.9) is True and at_least(0.8999, 0.9) is False


# ------------------------------------------------------------------ versions + lineage
def test_versions_are_numbered_per_model_start_in_stage_none_and_link_their_run(registry, make_run):
    r1, r2, r3 = make_run(metrics={"acc": 0.9}), make_run(metrics={"acc": 0.91}), make_run(metrics={"acc": 0.92})
    assert registry.register_version("churn", r1) == 1
    assert registry.register_version("churn", r2) == 2
    assert registry.register_version("fraud", r3) == 1, "numbering is independent per model"
    version = registry.get_version("churn", 2)
    assert (version.run_id, version.stage, version.validated) == (r2, Stage.NONE, False)
    assert [v.version for v in registry.list_versions("churn")] == [1, 2]
    with pytest.raises(ModelVersionNotFoundError):
        registry.get_version("churn", 9)


def test_only_finished_runs_with_full_lineage_can_be_registered(registry, make_run):
    running = make_run(metrics={"acc": 0.9}, finish=False)
    with pytest.raises(RegistryError):
        registry.register_version("churn", running)
    with pytest.raises(RegistryError):
        registry.register_version("churn", "run-does-not-exist")
    for missing in ({"dataset_hash": None}, {"code_version": None}, {"dataset_hash": "", "code_version": None}):
        with pytest.raises(LineageError):
            registry.register_version("churn", make_run(metrics={"acc": 0.9}, **missing))
    assert registry.list_versions("churn") == [], "failed registrations must not leave a version behind"


def test_lineage_reports_dataset_hash_code_version_params_and_artifact_hashes(registry, tracker, tmp_path):
    artifact = tmp_path / "model.pkl"
    artifact.write_bytes(b"pickled-model")
    run_id = tracker.start_run("exp", dataset_hash="sha256:data-7", code_version="git:9f8e7d6")
    tracker.log_param(run_id, "lr", 0.05)
    digest = tracker.log_artifact(run_id, artifact)
    tracker.end_run(run_id)
    version = registry.register_version("churn", run_id)

    lineage = registry.lineage("churn", version)
    assert (lineage.run_id, lineage.dataset_hash, lineage.code_version) == (run_id, "sha256:data-7", "git:9f8e7d6")
    assert lineage.params == {"lr": "0.05"} and lineage.artifacts == {"model.pkl": digest}


# ------------------------------------------------------------------ stage machine
def test_stage_transitions_follow_none_staging_production_archived(registry, stage_version):
    version = stage_version(0.95)
    assert registry.get_version("churn", version).stage is Stage.STAGING
    registry.transition("churn", version, Stage.PRODUCTION, policy=POLICY)
    assert registry.get_version("churn", version).stage is Stage.PRODUCTION
    registry.transition("churn", version, Stage.ARCHIVED, reason="retired")
    assert registry.get_version("churn", version).stage is Stage.ARCHIVED


def test_illegal_transitions_are_rejected_and_change_nothing(registry, make_run, stage_version):
    fresh = registry.register_version("churn", make_run(metrics={"acc": 0.95}))
    with pytest.raises(InvalidTransitionError):
        registry.transition("churn", fresh, Stage.PRODUCTION, policy=POLICY)  # cannot skip Staging
    with pytest.raises(InvalidTransitionError):
        registry.transition("churn", fresh, Stage.NONE)
    registry.transition("churn", fresh, Stage.ARCHIVED)
    with pytest.raises(InvalidTransitionError):
        registry.transition("churn", fresh, Stage.STAGING)  # Archived is terminal
    staged = stage_version(0.95)
    with pytest.raises(InvalidTransitionError):
        registry.transition("churn", staged, Stage.STAGING)  # same stage again
    with pytest.raises(ValueError):
        registry.transition("churn", staged, Stage.PRODUCTION)  # Production always needs a PromotionPolicy
    assert registry.get_version("churn", fresh).stage is Stage.ARCHIVED
    assert [e.to_stage for e in registry.history("churn") if e.version == fresh] == [Stage.ARCHIVED]


# ------------------------------------------------------------------ promotion gates
def test_threshold_gate_blocks_below_and_allows_exactly_at_the_threshold(registry, stage_version):
    below = stage_version(0.8999)
    result = registry.check_promotion("churn", below, POLICY)
    assert not result.passed and any("threshold" in reason for reason in result.reasons)
    with pytest.raises(PromotionBlockedError):
        registry.transition("churn", below, Stage.PRODUCTION, policy=POLICY)
    assert registry.get_version("churn", below).stage is Stage.STAGING

    exact = stage_version(0.90)
    assert registry.check_promotion("churn", exact, POLICY).passed, "0.90 meets a 0.90 threshold"


def test_margin_gate_uses_float_safe_comparison_against_current_production(registry, stage_version):
    incumbent = stage_version(0.933)
    registry.transition("churn", incumbent, Stage.PRODUCTION, policy=POLICY)

    too_small = stage_version(0.937)
    result = registry.check_promotion("churn", too_small, POLICY)
    assert not result.passed and any("margin" in reason for reason in result.reasons)

    enough = stage_version(0.938)  # 0.938 - 0.933 == 0.004999999999999893 in floating point
    assert registry.check_promotion("churn", enough, POLICY).passed, "an improvement of exactly 0.005 must pass"
    registry.transition("churn", enough, Stage.PRODUCTION, policy=POLICY)


def test_margin_gate_is_skipped_when_nothing_is_in_production_yet(registry, stage_version):
    version = stage_version(0.90)
    policy = PromotionPolicy("acc", 0.90, min_improvement=0.5)
    assert registry.check_promotion("churn", version, policy).passed


def test_lower_is_better_metrics_flip_the_threshold_and_margin(registry, stage_version):
    policy = PromotionPolicy("loss", threshold=0.30, min_improvement=0.02, higher_is_better=False)
    incumbent = stage_version(0.9, extra={"loss": 0.25})
    registry.transition("churn", incumbent, Stage.PRODUCTION, policy=policy)

    worse = stage_version(0.9, extra={"loss": 0.24})  # only 0.01 better than production
    assert not registry.check_promotion("churn", worse, policy).passed
    over_threshold = stage_version(0.9, extra={"loss": 0.31})
    assert not registry.check_promotion("churn", over_threshold, policy).passed
    better = stage_version(0.9, extra={"loss": 0.22})
    assert registry.check_promotion("churn", better, policy).passed


def test_unvalidated_versions_are_blocked_unless_the_policy_waives_validation(registry, stage_version):
    version = stage_version(0.95, validated=False)
    result = registry.check_promotion("churn", version, POLICY)
    assert not result.passed and any("validated" in reason for reason in result.reasons)
    waived = PromotionPolicy("acc", 0.90, require_validated=False)
    assert registry.check_promotion("churn", version, waived).passed
    registry.mark_validated("churn", version)
    assert registry.check_promotion("churn", version, POLICY).passed


def test_open_data_quality_flags_block_promotion_until_resolved(registry, stage_version):
    version = stage_version(0.95)
    flag = registry.add_quality_flag("churn", version, "label leakage suspected in column tenure")
    other = registry.add_quality_flag("churn", version, "null rate spiked")
    result = registry.check_promotion("churn", version, POLICY)
    assert not result.passed and any("2 open" in reason for reason in result.reasons)

    registry.resolve_quality_flag(flag)
    assert registry.open_quality_flags("churn", version) == ["null rate spiked"]
    registry.resolve_quality_flag(other)
    assert registry.check_promotion("churn", version, POLICY).passed
    with pytest.raises(RegistryError):
        registry.resolve_quality_flag(other)  # already resolved


def test_a_run_without_the_policy_metric_is_blocked(registry, stage_version):
    version = stage_version(0.95)
    result = registry.check_promotion("churn", version, PromotionPolicy("auc", 0.5))
    assert not result.passed and any("auc" in reason for reason in result.reasons)


def test_every_failing_gate_is_reported_together_and_nothing_changes(registry, stage_version):
    incumbent = stage_version(0.95)
    registry.transition("churn", incumbent, Stage.PRODUCTION, policy=POLICY)
    bad = stage_version(0.80, validated=False)
    registry.add_quality_flag("churn", bad, "duplicated rows")

    with pytest.raises(PromotionBlockedError) as caught:
        registry.transition("churn", bad, Stage.PRODUCTION, policy=POLICY)
    assert len(caught.value.reasons) == 4, f"threshold, margin, validation and flag: {caught.value.reasons}"
    assert registry.get_version("churn", bad).stage is Stage.STAGING
    assert registry.get_version("churn", incumbent).stage is Stage.PRODUCTION, "a blocked promotion must not demote production"


def test_promoting_archives_the_previous_production_so_only_one_is_live(registry, stage_version):
    v1 = stage_version(0.91)
    registry.transition("churn", v1, Stage.PRODUCTION, policy=POLICY)
    v2 = stage_version(0.95)
    registry.transition("churn", v2, Stage.PRODUCTION, policy=POLICY)
    stages = {v.version: v.stage for v in registry.list_versions("churn")}
    assert stages == {v1: Stage.ARCHIVED, v2: Stage.PRODUCTION}
    assert registry.latest("churn", Stage.PRODUCTION) == v2
    assert registry.latest("churn", Stage.NONE) is None


# ------------------------------------------------------------------ rollback + history
def test_rollback_restores_the_superseded_version_and_records_why(registry, stage_version):
    v1 = stage_version(0.91)
    registry.transition("churn", v1, Stage.PRODUCTION, policy=POLICY)
    v2 = stage_version(0.95)
    registry.transition("churn", v2, Stage.PRODUCTION, policy=POLICY)

    assert registry.rollback("churn", reason="latency regression") == v1
    stages = {v.version: v.stage for v in registry.list_versions("churn")}
    assert stages == {v1: Stage.PRODUCTION, v2: Stage.ARCHIVED}
    last_two = registry.history("churn")[-2:]
    assert [(e.version, e.from_stage, e.to_stage) for e in last_two] == [
        (v2, Stage.PRODUCTION, Stage.ARCHIVED),
        (v1, Stage.ARCHIVED, Stage.PRODUCTION),
    ]
    assert all("latency regression" in e.reason for e in last_two)


def test_rollback_is_an_emergency_action_that_ignores_promotion_gates(registry, stage_version):
    v1 = stage_version(0.91)
    registry.transition("churn", v1, Stage.PRODUCTION, policy=POLICY)
    v2 = stage_version(0.95)
    registry.transition("churn", v2, Stage.PRODUCTION, policy=POLICY)
    v3 = stage_version(0.97)
    registry.transition("churn", v3, Stage.PRODUCTION, policy=POLICY)
    registry.add_quality_flag("churn", v2, "flag raised after v2 was retired")
    assert registry.rollback("churn") == v2, "roll back to the MOST RECENT predecessor, not the oldest"
    assert registry.get_version("churn", v1).stage is Stage.ARCHIVED


def test_rollback_without_production_or_without_history_raises(registry, stage_version):
    with pytest.raises(RollbackError):
        registry.rollback("churn")  # nothing at all
    only = stage_version(0.95)
    registry.transition("churn", only, Stage.PRODUCTION, policy=POLICY)
    with pytest.raises(RollbackError):
        registry.rollback("churn")  # production has no predecessor
    assert registry.get_version("churn", only).stage is Stage.PRODUCTION


def test_stage_changes_persist_and_history_is_ordered(db_path, registry, stage_version, clock):
    version = stage_version(0.95)
    clock.advance(60)
    registry.transition("churn", version, Stage.PRODUCTION, policy=POLICY, reason="go live")

    with Registry(db_path) as reopened:
        assert reopened.get_version("churn", version).stage is Stage.PRODUCTION
        events = reopened.history("churn")
    assert [(e.from_stage, e.to_stage) for e in events] == [
        (Stage.NONE, Stage.STAGING),
        (Stage.STAGING, Stage.PRODUCTION),
    ]
    assert events[0].seq < events[1].seq and events[1].reason == "go live"
    assert events[1].at > events[0].at
