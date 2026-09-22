"""Prevention: the cache must stay bounded no matter how many distinct queries arrive."""
import service


def test_cache_is_bounded():
    for i in range(5000):
        service.get_report("one-off %d" % i)
    assert len(service._CACHE) <= service.MAX_ENTRIES


def test_hot_query_survives_churn():
    service.get_report("hot")
    for i in range(service.MAX_ENTRIES // 2):
        service.get_report("cold %d" % i)
        service.get_report("hot")
    before = service.STATS["computes"]
    service.get_report("hot")
    assert service.STATS["computes"] == before
