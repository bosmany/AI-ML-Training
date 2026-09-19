import subprocess

import pytest
from helpers import FakeRunner, fail, load, ok, timeout_error

from lab import Kubectl, KubectlError, build_report, render_report, triage_cluster


def test_get_pods_builds_a_list_command_without_shell_and_with_timeout():
    runner = FakeRunner(default=ok({"items": []}))
    Kubectl(runner, timeout=12).get_pods("prod")
    cmd, kwargs = runner.calls[0]
    assert cmd == ["kubectl", "get", "pods", "-n", "prod", "-o", "json"], "argv must be a list, never a joined string"
    assert kwargs["timeout"] == 12, "every subprocess call needs a timeout"
    assert not kwargs.get("shell"), "never shell=True"
    assert kwargs["capture_output"] is True and kwargs["text"] is True
    assert kwargs.get("check") is False, "we inspect returncode ourselves to include stderr in the error"


def test_all_namespaces_nodes_and_context_flags():
    runner = FakeRunner(default=ok({"items": []}))
    k = Kubectl(runner, context="kind-lab")
    k.get_pods()
    k.get_nodes()
    assert runner.calls[0][0] == ["kubectl", "--context", "kind-lab", "get", "pods", "--all-namespaces", "-o", "json"]
    assert runner.calls[1][0] == ["kubectl", "--context", "kind-lab", "get", "nodes", "-o", "json"]


def test_returns_parsed_json():
    assert Kubectl(FakeRunner(default=ok({"items": [1, 2]}))).get_nodes() == {"items": [1, 2]}


def test_non_zero_exit_raises_with_stderr_and_returncode():
    k = Kubectl(FakeRunner(default=fail(1, 'Error from server (Forbidden): pods is forbidden\n')))
    with pytest.raises(KubectlError) as info:
        k.get_pods("prod")
    assert info.value.returncode == 1
    assert "Forbidden" in info.value.stderr and "Forbidden" in str(info.value), "the reason must not be lost"
    assert info.value.cmd[:2] == ["kubectl", "get"]


def test_timeout_missing_binary_and_bad_json_become_kubectl_errors():
    with pytest.raises(KubectlError, match="timed out"):
        Kubectl(FakeRunner(default=timeout_error()), timeout=1).get_nodes()
    with pytest.raises(KubectlError, match="not found"):
        Kubectl(FakeRunner(default=FileNotFoundError())).get_nodes()
    bad = type("R", (), {"returncode": 0, "stdout": "<html>", "stderr": ""})()
    with pytest.raises(KubectlError, match="JSON"):
        Kubectl(FakeRunner(default=bad)).get_nodes()


def test_namespace_that_looks_like_a_flag_is_rejected_before_running_anything():
    runner = FakeRunner(default=ok({}))
    for evil in ["--all-namespaces", "-A", "prod; rm -rf /", "", "a b", "$(id)"]:
        with pytest.raises(ValueError):
            Kubectl(runner).get_pods(evil)
    assert runner.calls == [], "validation happens before the subprocess call"


def test_default_runner_is_subprocess_run():
    assert Kubectl()._runner is subprocess.run


def test_triage_cluster_uses_the_wrapper_and_summarises_problems():
    runner = FakeRunner({
        ("get", "pods", "--all-namespaces", "-o", "json"): ok(load("pods.json")),
        ("get", "nodes", "-o", "json"): ok(load("nodes.json")),
    })
    report = triage_cluster(Kubectl(runner))
    names = [f"{p.namespace}/{p.name}" for p in report.pods_with_problems]
    assert names == sorted(names, key=lambda s: tuple(s.split("/"))), "sorted by namespace then name"
    assert set(names) == {"prod/api-crash", "batch/worker-oom", "prod/img-bad", "dev/img-err", "dev/big-pending",
                          "prod/evicted-pod", "dev/init-fail"}
    assert [n.name for n in report.nodes_with_problems] == ["node-2", "node-3"]
    assert len(runner.calls) == 2


def test_render_report_lists_problems_and_totals():
    report = build_report(load("pods.json"), load("nodes.json"))
    text = render_report(report)
    assert "node-2" in text and "NotReady" in text
    assert "prod/api-crash" in text and "CrashLoopBackOff" in text
    assert "prod: 3 pods, cpu req 700m / lim 800m" in text
    healthy = render_report(build_report({"items": []}, {"items": []}))
    assert healthy.count("none") == 2
