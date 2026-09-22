import service


def test_report_shape():
    r = service.get_report("Hello World")
    assert r["query"] == "hello world"
    assert len(r["digest"]) == 64
    assert len(r["rows"]) == 16


def test_spellings_are_equivalent():
    assert service.get_report("  Foo  BAR ") == service.get_report("foo bar")


def test_different_queries_differ():
    assert service.get_report("alpha")["digest"] != service.get_report("beta")["digest"]


def test_repeat_query_is_served_from_cache():
    service.get_report("cache-me-once")
    before = service.STATS["computes"]
    for _ in range(5):
        service.get_report("cache-me-once")
    assert service.STATS["computes"] == before
