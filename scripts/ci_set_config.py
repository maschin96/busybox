#!/usr/bin/env python3
"""Set boolean BusyBox .config symbols for CI jobs."""

from pathlib import Path
import sys


def set_bool(text: str, name: str, enabled: bool) -> str:
    disabled_line = f"# CONFIG_{name} is not set"
    enabled_line = f"CONFIG_{name}=y"

    if enabled:
        if disabled_line in text:
            return text.replace(disabled_line, enabled_line)
        if enabled_line in text:
            return text
    else:
        if enabled_line in text:
            return text.replace(enabled_line, disabled_line)
        if disabled_line in text:
            return text

    raise SystemExit(f"CONFIG_{name} not found")


def parse_assignment(arg: str) -> tuple[str, bool]:
    if "=" not in arg:
        raise SystemExit(f"expected SYMBOL=y or SYMBOL=n, got {arg!r}")

    name, value = arg.split("=", 1)
    if not name:
        raise SystemExit(f"empty symbol in {arg!r}")
    if name.startswith("CONFIG_"):
        name = name[len("CONFIG_") :]

    if value == "y":
        return name, True
    if value == "n":
        return name, False
    raise SystemExit(f"unsupported value in {arg!r}: use y or n")


def main(argv: list[str]) -> int:
    config = Path(".config")
    if argv[:1] == ["--config"]:
        if len(argv) < 3:
            raise SystemExit(
                "usage: scripts/ci_set_config.py [--config PATH] SYMBOL=y [SYMBOL=n ...]"
            )
        config = Path(argv[1])
        argv = argv[2:]

    if not argv:
        raise SystemExit(
            "usage: scripts/ci_set_config.py [--config PATH] SYMBOL=y [SYMBOL=n ...]"
        )

    text = config.read_text()
    for arg in argv:
        name, enabled = parse_assignment(arg)
        text = set_bool(text, name, enabled)
    config.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
