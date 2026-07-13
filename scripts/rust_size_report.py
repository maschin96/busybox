#!/usr/bin/env python3
"""Report binary size deltas for opt-in Rust applets."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

import compare_rust_applets


DEFAULT_BUILD_DIR = compare_rust_applets.REPO_ROOT / "build" / "rust-size-report"


@dataclass(frozen=True)
class SizeRow:
    target: str
    c_text: int
    c_data: int
    c_bss: int
    c_dec: int
    rust_text: int
    rust_data: int
    rust_bss: int
    rust_dec: int

    @property
    def delta_dec(self) -> int:
        return self.rust_dec - self.c_dec


@dataclass(frozen=True)
class SymbolRow:
    applet: str
    c_main: int | None
    rust_shim: int | None
    rust_entry: int | None


def run_capture(argv: list[str], *, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def binary_size(path: Path) -> tuple[int, int, int, int]:
    output = run_capture(["size", str(path)])
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0].isdigit():
            text, data, bss, dec = (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
            return text, data, bss, dec
    raise RuntimeError(f"could not parse size output for {path}: {output!r}")


def symbol_sizes(path: Path) -> dict[str, int]:
    output = run_capture(["nm", "-S", "--size-sort", str(path)])
    sizes: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            _, size_hex, _, name = parts[:4]
            try:
                sizes[name] = int(size_hex, 16)
            except ValueError:
                continue
    return sizes


def size_rows(c_dir: Path, rust_dir: Path) -> list[SizeRow]:
    rows: list[SizeRow] = []
    for target in ("busybox", "busybox_unstripped"):
        c_text, c_data, c_bss, c_dec = binary_size(c_dir / target)
        rust_text, rust_data, rust_bss, rust_dec = binary_size(rust_dir / target)
        rows.append(
            SizeRow(
                target=target,
                c_text=c_text,
                c_data=c_data,
                c_bss=c_bss,
                c_dec=c_dec,
                rust_text=rust_text,
                rust_data=rust_data,
                rust_bss=rust_bss,
                rust_dec=rust_dec,
            )
        )
    return rows


def symbol_rows(c_dir: Path, rust_dir: Path, applets: list[str]) -> list[SymbolRow]:
    c_symbols = symbol_sizes(c_dir / "busybox_unstripped")
    rust_symbols = symbol_sizes(rust_dir / "busybox_unstripped")
    rows: list[SymbolRow] = []
    for applet in applets:
        rows.append(
            SymbolRow(
                applet=applet,
                c_main=c_symbols.get(f"{applet}_main"),
                rust_shim=rust_symbols.get(f"{applet}_main"),
                rust_entry=rust_symbols.get(f"rust_{applet}_main"),
            )
        )
    return rows


def rust_archive_size(rust_dir: Path) -> int:
    archive = rust_dir / "rust" / "target" / "release" / "libbusybox_rs.a"
    return archive.stat().st_size


def format_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    return str(value)


def print_markdown(
    *,
    applets: list[str],
    c_dir: Path,
    rust_dir: Path,
    rows: list[SizeRow],
    symbols: list[SymbolRow],
) -> None:
    print("# Rust Applet Size Report")
    print()
    print(f"- Applets: {', '.join(applets)}")
    print(f"- C build: `{c_dir}`")
    print(f"- Rust build: `{rust_dir}`")
    print(f"- Rust static archive: `{rust_archive_size(rust_dir)}` bytes")
    print()
    print("## Binary Totals")
    print()
    print("| target | c text | c data | c bss | c total | rust text | rust data | rust bss | rust total | delta |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in rows:
        print(
            f"| {row.target} | {row.c_text} | {row.c_data} | {row.c_bss} | {row.c_dec} | "
            f"{row.rust_text} | {row.rust_data} | {row.rust_bss} | {row.rust_dec} | {row.delta_dec:+d} |"
        )
    print()
    print("## Applet Symbols")
    print()
    print("| applet | c `<applet>_main` | rust C shim | rust entry |")
    print("| --- | ---: | ---: | ---: |")
    for symbol in symbols:
        print(
            f"| {symbol.applet} | {format_bytes(symbol.c_main)} | "
            f"{format_bytes(symbol.rust_shim)} | {format_bytes(symbol.rust_entry)} |"
        )


def print_json(
    *,
    applets: list[str],
    c_dir: Path,
    rust_dir: Path,
    rows: list[SizeRow],
    symbols: list[SymbolRow],
) -> None:
    payload = {
        "applets": applets,
        "c_build": str(c_dir),
        "rust_build": str(rust_dir),
        "rust_static_archive_bytes": rust_archive_size(rust_dir),
        "binaries": [
            {
                "target": row.target,
                "c": {"text": row.c_text, "data": row.c_data, "bss": row.c_bss, "total": row.c_dec},
                "rust": {
                    "text": row.rust_text,
                    "data": row.rust_data,
                    "bss": row.rust_bss,
                    "total": row.rust_dec,
                },
                "delta_total": row.delta_dec,
            }
            for row in rows
        ],
        "symbols": [
            {
                "applet": symbol.applet,
                "c_main": symbol.c_main,
                "rust_c_shim": symbol.rust_shim,
                "rust_entry": symbol.rust_entry,
            }
            for symbol in symbols
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build C/Rust BusyBox variants and report binary size deltas."
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=DEFAULT_BUILD_DIR,
        help=f"build directory (default: {DEFAULT_BUILD_DIR})",
    )
    parser.add_argument("--c-build-dir", type=Path, help="existing C build directory")
    parser.add_argument("--rust-build-dir", type=Path, help="existing Rust build directory")
    parser.add_argument(
        "--applet",
        action="append",
        choices=sorted(compare_rust_applets.APPLETS),
        help="applet to include; may be passed multiple times",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="report format (default: markdown)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    applets = args.applet or sorted(compare_rust_applets.APPLETS)

    if bool(args.c_build_dir) != bool(args.rust_build_dir):
        raise SystemExit("--c-build-dir and --rust-build-dir must be provided together")
    if args.c_build_dir and args.rust_build_dir:
        c_dir = args.c_build_dir.resolve()
        rust_dir = args.rust_build_dir.resolve()
    else:
        c_binary, rust_binary = compare_rust_applets.build_binaries(
            args.build_dir,
            applets,
            quiet=True,
        )
        c_dir = c_binary.parent
        rust_dir = rust_binary.parent

    rows = size_rows(c_dir, rust_dir)
    symbols = symbol_rows(c_dir, rust_dir, applets)
    if args.format == "json":
        print_json(applets=applets, c_dir=c_dir, rust_dir=rust_dir, rows=rows, symbols=symbols)
    else:
        print_markdown(applets=applets, c_dir=c_dir, rust_dir=rust_dir, rows=rows, symbols=symbols)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
