"""Prevention: adversarial input must stay fast, and the validators must stay linear-time."""
import time

from validators import is_valid_tag_list, is_valid_username


def _fast(fn, text):
    t = time.perf_counter()
    fn(text)
    return time.perf_counter() - t


def test_username_is_not_exponential():
    assert _fast(is_valid_username, "a" * 60 + "!") < 0.05


def test_tags_are_not_exponential():
    assert _fast(is_valid_tag_list, "a" * 250 + "!") < 0.05
