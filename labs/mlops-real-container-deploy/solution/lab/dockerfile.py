"""A small, dependency-free Dockerfile parser (enough for policy checks; not a full BuildKit parser).

Reused as-is from labs/fastapi-deploy-cicd's lab/dockerfile.py - it is a generic Dockerfile parser, not
specific to that lab's app, so it applies here unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from lab.errors import AssetError


@dataclass(frozen=True)
class Instruction:
    keyword: str  # upper-cased: RUN, COPY, USER ...
    args: str  # everything after the keyword, continuation lines joined
    line: int  # 1-based line where the instruction starts
    stage: int  # index of the build stage it belongs to (-1 for ARGs before the first FROM)

    @property
    def is_exec_form(self) -> bool:
        return self.exec_args() is not None

    def exec_args(self) -> list[str] | None:
        """The JSON-array form ``["a", "b"]`` as a list, or None for shell form."""
        text = self.args.strip()
        if text.startswith("["):
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                return None
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return value
        return None

    def flags(self) -> dict[str, str]:
        """Leading ``--name=value`` options (COPY --from=builder, HEALTHCHECK --interval=30s, ...)."""
        found: dict[str, str] = {}
        for token in self.args.split():
            if not token.startswith("--"):
                break
            name, _, value = token[2:].partition("=")
            found[name] = value
        return found


@dataclass
class Stage:
    index: int
    base: str  # image reference as written after FROM (variables already resolved when possible)
    alias: str | None
    instructions: list[Instruction] = field(default_factory=list)  # excludes the FROM itself

    def of(self, keyword: str) -> list[Instruction]:
        return [i for i in self.instructions if i.keyword == keyword]


@dataclass
class Dockerfile:
    stages: list[Stage]
    global_args: dict[str, str]

    @property
    def final(self) -> Stage:
        return self.stages[-1]

    def all_instructions(self) -> list[Instruction]:
        return [i for stage in self.stages for i in stage.instructions]


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash continuations, drop comments and blanks. Returns (start_line, text)."""
    result: list[tuple[int, str]] = []
    buffer = ""
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue  # Docker also strips comment lines in the middle of a continuation
        if not buffer:
            if not stripped:
                continue
            start = number
        if stripped.endswith("\\"):
            buffer += stripped[:-1].rstrip() + " "
            continue
        buffer += stripped
        result.append((start, buffer))
        buffer = ""
    if buffer:
        result.append((start, buffer.strip()))
    return result


def _resolve(value: str, args: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return args.get(name, match.group(0))

    return re.sub(r"\$\{(\w+)\}|\$(\w+)", replace, value)


def parse_dockerfile(text: str) -> Dockerfile:
    """Parse ``text`` into stages. Raises ``AssetError`` if there is no ``FROM`` at all."""
    global_args: dict[str, str] = {}
    stages: list[Stage] = []
    for number, line in _logical_lines(text):
        keyword, _, rest = line.partition(" ")
        keyword = keyword.upper()
        rest = rest.strip()
        if keyword == "FROM":
            tokens = [t for t in rest.split() if not t.startswith("--")]
            if not tokens:
                raise AssetError(f"Dockerfile line {number}: FROM needs an image")
            alias = tokens[2] if len(tokens) >= 3 and tokens[1].upper() == "AS" else None
            stages.append(Stage(len(stages), _resolve(tokens[0], global_args), alias))
        elif not stages:
            if keyword == "ARG":
                name, _, default = rest.partition("=")
                global_args[name.strip()] = default.strip().strip("\"'")
            # anything else before FROM is invalid; ignore it
        else:
            stages[-1].instructions.append(Instruction(keyword, rest, number, len(stages) - 1))
    if not stages:
        raise AssetError("Dockerfile has no FROM instruction - write it (see the README tasks)")
    return Dockerfile(stages, global_args)


def split_image(reference: str) -> tuple[str, str | None, str | None]:
    """Split ``registry:5000/team/img:1.2@sha256:abc`` into ``(name, tag, digest)``."""
    digest = None
    if "@" in reference:
        reference, _, digest = reference.partition("@")
    last = reference.rsplit("/", 1)[-1]
    if ":" in last:
        name, _, tag = reference.rpartition(":")
        return name, tag, digest
    return reference, None, digest
