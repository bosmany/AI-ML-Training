import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber
from helpers import Sleeper, client_error, count_calls, inject_error

from lab import is_retryable, list_all, make_client, retry_call


def test_make_client_pins_region_timeouts_and_disables_botocore_retries():
    c = make_client("ec2", region="eu-west-1")
    assert c.meta.region_name == "eu-west-1"
    assert c.meta.config.retries["total_max_attempts"] == 1, "our retry_call owns retries; botocore must not also sleep"
    assert c.meta.config.connect_timeout and c.meta.config.read_timeout, "always set timeouts"


def test_is_retryable_only_for_throttling_style_client_errors():
    assert is_retryable(client_error("Throttling"))
    assert is_retryable(client_error("RequestLimitExceeded"))
    assert not is_retryable(client_error("AccessDenied")), "permission errors never fix themselves"
    assert not is_retryable(ValueError("x"))


def test_retry_call_returns_immediately_on_success_without_sleeping():
    sleeper = Sleeper()
    assert retry_call(lambda: 42, sleep=sleeper) == 42
    assert sleeper.delays == []


def test_retry_call_backs_off_exponentially_then_succeeds():
    sleeper = Sleeper()
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 4:
            raise client_error("Throttling")
        return "ok"

    assert retry_call(flaky, sleep=sleeper, base_delay=0.5) == "ok"
    assert sleeper.delays == [0.5, 1.0, 2.0], "delay doubles each retry: base * 2**n"


def test_retry_call_caps_the_delay_and_raises_last_error_after_max_attempts():
    sleeper = Sleeper()
    calls = []

    def always():
        calls.append(1)
        raise client_error("ServiceUnavailable")

    with pytest.raises(ClientError) as info:
        retry_call(always, max_attempts=5, base_delay=1.0, max_delay=3.0, sleep=sleeper)
    assert info.value.response["Error"]["Code"] == "ServiceUnavailable"
    assert len(calls) == 5
    assert sleeper.delays == [1.0, 2.0, 3.0, 3.0], "4 sleeps between 5 attempts, capped at max_delay"


def test_retry_call_does_not_retry_non_retryable_or_non_client_errors():
    sleeper = Sleeper()
    with pytest.raises(ClientError):
        retry_call(lambda: (_ for _ in ()).throw(client_error("AccessDenied")), sleep=sleeper)
    with pytest.raises(EndpointConnectionError):
        retry_call(lambda: (_ for _ in ()).throw(EndpointConnectionError(endpoint_url="http://x")), sleep=sleeper)
    assert sleeper.delays == [], "no sleeping for errors that retrying cannot fix"


def test_list_all_walks_every_page_of_a_real_paginated_api(ec2, ami):
    for _ in range(12):  # one reservation each -> EC2 paginates by reservation
        ec2.run_instances(ImageId=ami, MinCount=1, MaxCount=1)
    seen = count_calls(ec2, "ec2.DescribeInstances")
    reservations = list_all(ec2, "describe_instances", "Reservations", page_size=5)
    assert len(reservations) == 12, "items from ALL pages must be returned"
    assert seen["calls"] == 3, "12 items at page size 5 = 3 API calls (5+5+2)"


def test_list_all_follows_tokens_for_apis_moto_does_not_paginate(iam):
    """Stubber gives us a scripted 3-page IAM listing (moto ignores MaxItems, real IAM does not)."""
    def user(n):
        return {"Path": "/", "UserName": n, "UserId": n * 16, "Arn": f"arn:aws:iam::123456789012:user/{n}",
                "CreateDate": "2024-01-01T00:00:00Z"}

    with Stubber(iam) as stub:
        stub.add_response("list_users", {"Users": [user("a"), user("b")], "IsTruncated": True, "Marker": "m1"})
        stub.add_response("list_users", {"Users": [user("c"), user("d")], "IsTruncated": True, "Marker": "m2"})
        stub.add_response("list_users", {"Users": [user("e")], "IsTruncated": False})
        names = [u["UserName"] for u in list_all(iam, "list_users", "Users", page_size=2)]
        stub.assert_no_pending_responses()
    assert names == ["a", "b", "c", "d", "e"]
    assert list_all(iam, "list_users", "Users", page_size=2) == [], "an empty listing is [] not an error"


def test_list_all_restarts_after_mid_listing_throttle_without_duplicates(ec2, ami):
    for _ in range(7):
        ec2.run_instances(ImageId=ami, MinCount=1, MaxCount=1)
    # First call fine (page 1), second call throttled once, then everything works.
    state = {"n": 0}

    def flaky_second_call(**_):
        state["n"] += 1
        if state["n"] == 2:
            from types import SimpleNamespace
            return (SimpleNamespace(status_code=400, headers={}, content=b""),
                    {"Error": {"Code": "Throttling", "Message": "slow down"}})

    ec2.meta.events.register("before-call.ec2.DescribeInstances", flaky_second_call)
    sleeper = Sleeper()
    reservations = list_all(ec2, "describe_instances", "Reservations", page_size=5, sleep=sleeper)
    ids = [i["InstanceId"] for r in reservations for i in r["Instances"]]
    assert len(ids) == 7 and len(set(ids)) == 7, "a retry must not duplicate the items of the page already read"
    assert len(sleeper.delays) == 1


def test_list_all_gives_up_with_the_throttling_error(ec2):
    inject_error(ec2, "ec2.DescribeInstances", "Throttling")
    sleeper = Sleeper()
    with pytest.raises(ClientError) as info:
        list_all(ec2, "describe_instances", "Reservations", max_attempts=3, sleep=sleeper)
    assert info.value.response["Error"]["Code"] == "Throttling"
    assert len(sleeper.delays) == 2
