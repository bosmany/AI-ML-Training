"""Input validators used by the signup and tagging endpoints."""
import re

# 3-64 chars: letters/digits, with single '.', '_' or '-' separators allowed between (and after) runs.
_USERNAME = re.compile(r"^([a-zA-Z0-9]+[._-]?)+$")
# Comma separated tags, each made of word characters or '-'; one optional trailing comma.
_TAGS = re.compile(r"^([\w-]+,?)*$")
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def is_valid_username(value):
    return isinstance(value, str) and 3 <= len(value) <= 64 and bool(_USERNAME.match(value))


def is_valid_tag_list(value):
    return isinstance(value, str) and len(value) <= 256 and bool(_TAGS.match(value))


def is_valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and bool(_EMAIL.match(value))
