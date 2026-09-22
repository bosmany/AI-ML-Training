import pytest

from validators import is_valid_email, is_valid_tag_list, is_valid_username


@pytest.mark.parametrize("name", ["abc", "Bob_1", "a.b", "a-b-c", "user.name-1", "xy_", "A1b2C3", "a" * 64])
def test_username_accepts(name):
    assert is_valid_username(name)


@pytest.mark.parametrize("name", ["", "ab", "a b", "a--b", "-abc", ".abc", "a__b", "abc!", "a" * 65, None, 42])
def test_username_rejects(name):
    assert not is_valid_username(name)


@pytest.mark.parametrize("tags", ["", "a", "a,b", "ml-ops,python3,data_eng", "a,b,", "x-y"])
def test_tags_accept(tags):
    assert is_valid_tag_list(tags)


@pytest.mark.parametrize("tags", [",", "a,,b", ",a", "a b", "a;b", "a" * 257, None])
def test_tags_reject(tags):
    assert not is_valid_tag_list(tags)


def test_email():
    assert is_valid_email("a.b+c@example.co.uk")
    assert not is_valid_email("nope")
    assert not is_valid_email("a@b")
