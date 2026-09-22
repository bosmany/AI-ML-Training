"""Errors raised while loading the files you are supposed to write."""


class AssetError(Exception):
    """An asset is missing, empty, or not parseable. The message tells you what to do about it."""
