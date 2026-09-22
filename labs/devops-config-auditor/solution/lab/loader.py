"""YAML loading with line numbers. PROVIDED.

Only ``yaml.SafeLoader`` is used: it can build plain dicts/lists/str/int/float/bool/None and nothing else, so a
config file can never make the auditor import a module or run code (``!!python/object/apply:os.system`` is an error).
JSON files load too (JSON is a subset of YAML).
"""

from __future__ import annotations

from typing import Any

import yaml

from lab.models import ConfigParseError, Document


def pointer_join(base: str, *parts: object) -> str:
    """RFC 6901 JSON pointer: ``pointer_join("/a", "b/c", 0) == "/a/b~1c/0"``."""
    out = base
    for part in parts:
        out += "/" + str(part).replace("~", "~0").replace("/", "~1")
    return out


def _index(node: yaml.Node, pointer: str, lines: dict[str, int], path: frozenset[int]) -> None:
    if id(node) in path:  # recursive alias: stop instead of looping forever
        return
    path = path | {id(node)}
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                continue
            child = pointer_join(pointer, key_node.value)
            lines[child] = key_node.start_mark.line + 1
            _index(value_node, child, lines, path)
    elif isinstance(node, yaml.SequenceNode):
        for i, item in enumerate(node.value):
            child = pointer_join(pointer, i)
            lines[child] = item.start_mark.line + 1
            _index(item, child, lines, path)


def load_documents(text: str, filename: str) -> list[Document]:
    """Parse every YAML document in ``text``; empty documents are skipped. Raises ``ConfigParseError``."""
    docs: list[Document] = []
    loader = yaml.SafeLoader(text)
    try:
        while loader.check_node():
            node = loader.get_node()
            assert node is not None
            data: Any = loader.construct_document(node)  # also resolves anchors and ``<<`` merge keys
            if data is None:
                continue
            lines: dict[str, int] = {"": node.start_mark.line + 1}
            _index(node, "", lines, frozenset())
            docs.append(Document(filename, data, lines))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        problem = getattr(exc, "problem", None) or str(exc)
        raise ConfigParseError(
            filename, mark.line + 1 if mark else None, mark.column + 1 if mark else None, str(problem)
        ) from exc
    finally:
        loader.dispose()
    return docs
