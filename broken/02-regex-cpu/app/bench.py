"""Time a validator on a probe input.   python bench.py username 24   -> 'a' * 24 + '!'"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validators  # noqa: E402

FUNCS = {"username": validators.is_valid_username, "tags": validators.is_valid_tag_list,
         "email": validators.is_valid_email}

if __name__ == "__main__":
    which, n = sys.argv[1], int(sys.argv[2])
    text = "a" * n + "!"
    t = time.perf_counter()
    result = FUNCS[which](text)
    print("%s(len=%d) -> %s in %.4fs" % (which, len(text), result, time.perf_counter() - t))
