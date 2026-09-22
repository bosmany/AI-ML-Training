"""Crawling same-host pages, cancellation, the JSON report and the command line."""
import asyncio
import json

import pytest

from lab import CheckConfig, LinkResult, Report, Status, crawl, main, make_client

CFG = CheckConfig(concurrency=4, timeout=2.0, connect_timeout=2.0)


def run_crawl(site, path="/", depth=1, config=CFG):
    return asyncio.run(crawl(site.url(path), config, depth=depth))


def test_depth_controls_how_many_page_hops_are_followed(site):
    site.page("/", links=["/a", "/dead"])
    site.page("/a", links=["/b"])
    site.page("/b", links=["/c"])
    site.page("/c")
    r0 = run_crawl(site, depth=0)
    assert set(r0.results) == {site.url("/")}, "depth 0 checks only the start URL"
    assert site.count("/a") == 0
    site.requests.clear()
    r1 = run_crawl(site, depth=1)
    assert set(r1.results) == {site.url(p) for p in ("/", "/a", "/dead")}
    assert site.count("/b") == 0, "depth 1 checks the links of the start page but does not read /a"
    r2 = run_crawl(site, depth=2)
    assert set(r2.results) == {site.url(p) for p in ("/", "/a", "/dead", "/b")}
    assert [r.url for r in r2.broken] == [site.url("/dead")]


def test_pages_are_fetched_with_get_but_leaf_links_only_with_head(site):
    site.page("/", links=["/a", "/leaf"])
    site.page("/a", links=["/leaf2"])
    site.add("/leaf", body="x")
    site.add("/leaf2", body="x")
    run_crawl(site, depth=2)
    assert site.count("/", "GET") == 1 and site.count("/a", "GET") == 1, "pages we parse need their body"
    assert site.count("/leaf", "GET") == 1, "a same-host link inside the depth budget is a page we read too"
    assert site.count("/leaf2", "GET") == 0 and site.count("/leaf2", "HEAD") == 1


def test_only_same_host_pages_are_crawled_external_links_are_just_checked(site, other_site):
    other_site.page("/ext", links=["/secret-inner"])
    site.page("/", links=[other_site.url("/ext"), "/local"])
    site.page("/local")
    report = run_crawl(site, depth=3)
    assert report.results[other_site.url("/ext")].status is Status.OK, "external link is still checked"
    assert other_site.count("/ext", "GET") == 0, "but its page is never downloaded/parsed"
    assert other_site.count("/secret-inner") == 0


def test_cycles_and_shared_links_are_fetched_once_but_each_source_is_recorded(site):
    site.page("/", links=["/a", "/b", "/shared"])
    site.page("/a", links=["/", "/b", "/shared"])   # links back to the start page
    site.page("/b", links=["/a", "/shared"])
    site.add("/shared", body="x")
    report = run_crawl(site, depth=5)
    for path in ("/", "/a", "/b"):
        assert site.count(path, "GET") == 1, f"{path} was fetched more than once"
    assert site.count("/shared") == 1
    sources = sorted(s for s, t in report.edges if t == site.url("/shared"))
    assert sources == sorted([site.url("/"), site.url("/a"), site.url("/b")]), "the report keeps every linking page"
    assert len(report.results) == 4


def test_non_html_same_host_resources_are_not_parsed(site):
    site.page("/", links=["/data.json", "/doc.pdf"])
    site.add("/data.json", body='<a href="/hidden">x</a>', content_type="application/json")
    site.add("/doc.pdf", body='<a href="/hidden">x</a>', content_type="application/pdf")
    report = run_crawl(site, depth=3)
    assert site.count("/hidden") == 0 and site.url("/hidden") not in report.results


def test_the_json_report_lists_source_target_status_and_latency(site):
    site.page("/", links=["/ok", "/gone", "/moved"])
    site.add("/ok", body="x", delay=0.03)
    site.add("/moved", status=301, headers={"Location": "/ok"})
    report = run_crawl(site, depth=1)
    data = json.loads(json.dumps(report.to_json_dict()))  # must be plain JSON
    assert (data["start_url"], data["interrupted"], data["checked"], data["broken"]) == (site.url("/"), False, 4, 1)
    rows = {row["url"]: row for row in data["links"]}
    assert rows[site.url("/")]["source"] is None
    assert rows[site.url("/gone")]["source"] == site.url("/") and rows[site.url("/gone")]["status"] == "client_error"
    assert rows[site.url("/gone")]["http_status"] == 404
    assert rows[site.url("/moved")]["status"] == "redirect" and rows[site.url("/moved")]["final_url"] == site.url("/ok")
    assert rows[site.url("/ok")]["latency_ms"] >= 25 and isinstance(rows[site.url("/ok")]["latency_ms"], float)
    assert set(rows[site.url("/ok")]) >= {"source", "url", "status", "http_status", "final_url", "latency_ms"}


def test_cancelling_a_crawl_closes_the_client_leaves_no_tasks_and_keeps_a_partial_report(site):
    site.page("/", links=["/slow1", "/slow2", "/quick"])
    site.add("/slow1", hang=True)
    site.add("/slow2", hang=True)
    site.add("/quick", body="x")
    config = CheckConfig(concurrency=5, timeout=30.0, connect_timeout=5.0)
    clients = []

    def factory(cfg):
        clients.append(make_client(cfg))
        return clients[-1]

    report = Report(start_url=site.url("/"))

    async def scenario():
        task = asyncio.create_task(crawl(site.url("/"), config, depth=1, client_factory=factory, report=report))
        assert await asyncio.to_thread(site.wait_for_in_flight, 2), "both hanging requests should be in flight"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    leftover = asyncio.run(scenario())
    assert leftover == [], f"cancellation must not leave pending tasks behind: {leftover}"
    assert clients and clients[0].is_closed, "the HTTP client must be closed on cancellation"
    assert report.interrupted is True
    assert site.url("/") in report.results, "results finished before the cancel stay in the report"
    partial = report.to_json_dict()
    assert partial["interrupted"] is True and all(row["url"] in report.results for row in partial["links"])


def test_cli_exits_1_and_lists_broken_links_and_writes_the_json_report(site, tmp_path, capsys):
    site.page("/", links=["/ok", "/gone"])
    site.add("/ok", body="x")
    out_file = tmp_path / "report.json"
    code = main([site.url("/"), "--depth", "1", "--concurrency", "2", "--timeout", "2", "--report", str(out_file)])
    out = capsys.readouterr().out
    assert code == 1, "broken links must give a non-zero exit code"
    assert "BROKEN" in out and site.url("/gone") in out and site.url("/ok") not in out
    assert "checked 3 URLs, 1 broken" in out
    data = json.loads(out_file.read_text())
    assert data["broken"] == 1 and {r["status"] for r in data["links"]} == {"ok", "client_error"}
    site.add("/gone", body="back")
    assert main([site.url("/")]) == 0, "all links healthy -> exit code 0"
    assert "0 broken" in capsys.readouterr().out


def test_cli_rejects_bad_usage_with_exit_code_2(site, capsys):
    for argv in ([], [site.url("/"), "--concurrency", "0"], [site.url("/"), "--timeout", "-1"],
                 [site.url("/"), "--depth", "-1"], ["not-a-url"], [site.url("/"), "--retries", "x"]):
        assert main(argv) == 2, f"{argv} should be a usage error"
    assert site.count() == 0, "usage errors must be detected before any request is made"


def test_cli_passes_options_to_the_crawler(capsys):
    seen = {}

    async def fake_crawler(start_url, config, *, depth, report):
        seen.update(start_url=start_url, config=config, depth=depth)
        return report

    code = main(["http://example.invalid/", "--depth", "3", "--concurrency", "7", "--timeout", "1.5",
                 "--connect-timeout", "0.5", "--retries", "2"], crawler=fake_crawler)
    assert code == 0
    assert seen["depth"] == 3 and seen["start_url"] == "http://example.invalid/"
    assert seen["config"] == CheckConfig(concurrency=7, timeout=1.5, connect_timeout=0.5, retries=2)


def test_cli_on_interrupt_prints_and_writes_a_partial_report_and_exits_130(tmp_path, capsys):
    out_file = tmp_path / "partial.json"
    start = "http://127.0.0.1:9/"

    async def interrupted_crawler(start_url, config, *, depth, report):
        report.edges.append((None, start))
        report.results[start] = LinkResult(start, Status.OK, 200)
        report.edges.append((start, start + "x"))
        report.results[start + "x"] = LinkResult(start + "x", Status.TIMEOUT, error="timed out")
        raise KeyboardInterrupt

    code = main([start, "--report", str(out_file)], crawler=interrupted_crawler)
    out = capsys.readouterr().out
    assert code == 130
    assert "interrupted" in out and "checked 2 URLs, 1 broken" in out
    data = json.loads(out_file.read_text())
    assert data["interrupted"] is True and data["checked"] == 2 and len(data["links"]) == 2
