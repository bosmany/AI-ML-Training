from helpers import load

from lab import NODE_NOT_READY, namespace_totals, parse_node_list, parse_pod_list


def test_healthy_node_has_no_problems_and_parses_allocatable():
    n = {x.name: x for x in parse_node_list(load("nodes.json"))}["node-1"]
    assert n.ready and not n.unschedulable and n.problems == () and n.pressures == ()
    assert (n.allocatable_cpu_m, n.allocatable_mem) == (4000, 16 * 2**30)


def test_node_with_unknown_ready_condition_is_not_ready():
    n = {x.name: x for x in parse_node_list(load("nodes.json"))}["node-2"]
    assert not n.ready, "Ready=Unknown means the kubelet stopped reporting: NOT ready"
    assert [p.kind for p in n.problems] == [NODE_NOT_READY]
    assert (n.allocatable_cpu_m, n.allocatable_mem) == (3920, 8038564 * 1024)
    assert n.pressures == (), "Unknown pressure conditions are not 'True' pressure"


def test_disk_pressure_and_cordon_are_reported_on_a_ready_node():
    n = {x.name: x for x in parse_node_list(load("nodes.json"))}["node-3"]
    assert n.ready and n.unschedulable
    assert n.pressures == ("DiskPressure",)
    assert [p.kind for p in n.problems] == ["DiskPressure"], "a cordoned node is not itself a 'problem'; pressure is"


def test_namespace_totals_skip_finished_pods_and_sum_requests_and_limits():
    t = namespace_totals(parse_pod_list(load("pods.json")))
    assert list(t) == ["batch", "dev", "kube-system", "prod"]
    prod = t["prod"]
    assert prod.pods == 3, "the Evicted (Failed) pod no longer holds resources"
    assert (prod.cpu_request_m, prod.cpu_limit_m) == (700, 800)
    assert (prod.mem_request, prod.mem_limit) == (448 * 2**20, 576 * 2**20)


def test_namespace_totals_batch_ignores_succeeded_and_dev_counts_missing_limits():
    t = namespace_totals(parse_pod_list(load("pods.json")))
    assert (t["batch"].pods, t["batch"].cpu_request_m, t["batch"].cpu_limit_m) == (1, 250, 1000)
    dev = t["dev"]
    assert dev.cpu_request_m == 8000 + 100, "8 cores + init-fail main (init container max 50m is smaller than sum)"
    assert dev.cpu_limit_m == 200
    assert dev.mem_request == 16 * 2**30 + 100 * 2**20
    assert dev.containers_without_limits == 2, "img-err and big-pending run without limits"


def test_namespace_totals_handle_odd_quantity_formats_and_empty_input():
    ks = namespace_totals(parse_pod_list(load("pods.json")))["kube-system"]
    assert (ks.cpu_request_m, ks.cpu_limit_m) == (1500, 2000)
    assert (ks.mem_request, ks.mem_limit) == (129_000_000, 129_000_000), "129e6 and 129M are the same number"
    assert namespace_totals([]) == {}
