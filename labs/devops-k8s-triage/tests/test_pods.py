from helpers import load, pod_doc

from lab import (CRASH_LOOP, EVICTED, IMAGE_PULL, INIT_FAILED, OOM_KILLED, PENDING_UNSCHEDULABLE,
                 diagnose_pod, parse_pod_list, pod_resources, qos_class)


def pods():
    return {f"{p.namespace}/{p.name}": p for p in parse_pod_list(load("pods.json"))}


def kinds(key):
    return sorted(p.kind for p in pods()[key].problems)


def test_parse_pod_list_returns_all_pods_sorted_by_namespace_and_name():
    keys = list(pods())
    assert len(keys) == 10
    assert keys == sorted(keys, key=lambda k: tuple(k.split("/")))


def test_healthy_and_completed_pods_have_no_problems():
    assert kinds("prod/web-ok") == []
    assert kinds("batch/nightly-done") == []
    assert kinds("kube-system/metrics-agent") == []


def test_crashloopbackoff_is_detected_with_restart_count():
    (p,) = pods()["prod/api-crash"].problems
    assert p.kind == CRASH_LOOP and p.container == "api" and "12" in p.detail


def test_oomkilled_is_found_in_last_state_even_when_the_container_is_running_again():
    pod = pods()["batch/worker-oom"]
    assert pod.phase == "Running"
    assert [p.kind for p in pod.problems] == [OOM_KILLED], "the OOM is only visible in lastState.terminated"


def test_oomkilled_in_current_state_and_crashloop_are_both_reported():
    doc = pod_doc(status={"phase": "Running", "containerStatuses": [{
        "name": "c0", "restartCount": 5,
        "state": {"waiting": {"reason": "CrashLoopBackOff"}},
        "lastState": {"terminated": {"exitCode": 137, "reason": "OOMKilled"}}}]})
    assert sorted(p.kind for p in diagnose_pod(doc)) == [CRASH_LOOP, OOM_KILLED]
    current = pod_doc(status={"phase": "Failed", "containerStatuses": [{
        "name": "c0", "state": {"terminated": {"exitCode": 137, "reason": "OOMKilled"}}}]})
    assert [p.kind for p in diagnose_pod(current)] == [OOM_KILLED]


def test_image_pull_problems_cover_both_backoff_and_errimagepull():
    assert kinds("prod/img-bad") == [IMAGE_PULL]
    assert kinds("dev/img-err") == [IMAGE_PULL]


def test_pending_pod_with_insufficient_cpu_reports_scheduler_message():
    (p,) = pods()["dev/big-pending"].problems
    assert p.kind == PENDING_UNSCHEDULABLE and "Insufficient cpu" in p.detail
    assert pods()["dev/big-pending"].node is None


def test_evicted_pod_is_detected_from_status_reason():
    (p,) = pods()["prod/evicted-pod"].problems
    assert p.kind == EVICTED and "memory" in p.detail
    assert pods()["prod/evicted-pod"].phase == "Failed"


def test_failing_init_container_is_reported_against_the_init_container():
    (p,) = pods()["dev/init-fail"].problems
    assert p.kind == INIT_FAILED and p.container == "wait-for-db"
    assert "1" in p.detail, "mention the last exit code"


def test_init_container_terminated_with_error_and_pod_without_status_are_handled():
    doc = pod_doc(status={"phase": "Pending", "initContainerStatuses": [
        {"name": "i0", "state": {"terminated": {"exitCode": 2, "reason": "Error"}}}]})
    assert [p.kind for p in diagnose_pod(doc)] == [INIT_FAILED]
    doc.pop("status")
    assert diagnose_pod(doc) == []
    assert parse_pod_list(doc)[0].phase == "Unknown"


def test_qos_class_follows_the_kubernetes_rules():
    def spec(*resources, init=()):
        return pod_doc(containers=list(resources), init=list(init) or None)["spec"]
    g = {"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {"cpu": "1000m", "memory": "1024Mi"}}
    assert qos_class(spec(g)) == "Guaranteed", "1 == 1000m and 1Gi == 1024Mi: compare VALUES, not strings"
    assert qos_class(spec({"limits": {"cpu": "1", "memory": "1Gi"}})) == "Guaranteed", "requests default to limits"
    assert qos_class(spec({})) == "BestEffort"
    assert qos_class(spec({"requests": {"cpu": "100m"}})) == "Burstable", "requests without limits"
    assert qos_class(spec({"limits": {"cpu": "1"}})) == "Burstable", "memory limit missing"
    assert qos_class(spec(g, {})) == "Burstable", "one container without resources spoils Guaranteed"
    assert qos_class(spec(g, {"requests": {"cpu": "1"}, "limits": {"cpu": "2", "memory": "1Gi"}})) == "Burstable"
    assert qos_class(spec(g, init=[{}])) == "Burstable", "init containers count too"


def test_computed_qos_matches_what_the_api_server_reported_in_the_fixture():
    raw = {i["metadata"]["namespace"] + "/" + i["metadata"]["name"]: i["status"]["qosClass"] for i in load("pods.json")["items"]}
    got = {k: p.qos for k, p in pods().items()}
    assert got == raw


def test_pod_resources_sums_containers_and_uses_the_larger_of_init_and_sum():
    r = pod_resources(pod_doc(containers=[
        {"requests": {"cpu": "250m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}},
        {"requests": {"cpu": "0.5", "memory": "1e8"}},  # 1e8 bytes, no limits
    ])["spec"])
    assert (r.cpu_request_m, r.cpu_limit_m) == (750, 500)
    assert (r.mem_request, r.mem_limit) == (128 * 2**20 + 10**8, 256 * 2**20)
    assert r.containers_without_limits == 1
    init_heavy = pod_resources(pod_doc(containers=[{"requests": {"cpu": "100m"}}],
                                       init=[{"requests": {"cpu": "2"}}, {"requests": {"cpu": "1"}}])["spec"])
    assert init_heavy.cpu_request_m == 2000, "init containers run one at a time BEFORE the app: take the max"


def test_request_defaults_to_limit_when_only_limit_is_set():
    r = pod_resources(pod_doc(containers=[{"limits": {"cpu": "2", "memory": "1Gi"}}])["spec"])
    assert (r.cpu_request_m, r.mem_request) == (2000, 2**30)
