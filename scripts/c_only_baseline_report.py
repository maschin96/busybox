#!/usr/bin/env python3
"""Build and document the current C-only BusyBox baseline."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD_DIR = REPO_ROOT / "build" / "c-only-baseline"
COPY_EXCLUDED_DIRS = {
    ".git",
    "build",
    "__pycache__",
    "rust/target",
}

FEATURE_RICH_SYMBOLS = (
    "BUSYBOX=y",
    "SHOW_USAGE=y",
    "LONG_OPTS=y",
    "FEATURE_RUST_APPLETS=n",
    "TRUE=y",
    "FALSE=y",
    "BASENAME=y",
    "DIRNAME=y",
    "PWD=y",
    "CAT=y",
    "YES=y",
    "WHOAMI=y",
    "HOSTID=y",
    "ECHO=y",
    "PRINTENV=y",
    "TTY=y",
    "UNLINK=y",
    "RMDIR=y",
    "SYNC=y",
    "SLEEP=y",
    "LS=y",
    "CP=y",
    "MV=y",
    "RM=y",
    "MKDIR=y",
    "TOUCH=y",
    "DATE=y",
    "DD=y",
    "HEAD=y",
    "TAIL=y",
    "WC=y",
    "SORT=y",
    "UNIQ=y",
    "CUT=y",
    "TR=y",
    "TEST=y",
    "TEST1=y",
    "FIND=y",
    "GREP=y",
    "SED=y",
    "AWK=y",
    "ASH=y",
    "SH_IS_ASH=y",
    "TAR=y",
    "GZIP=y",
    "GUNZIP=y",
    "BUNZIP2=y",
    "BZCAT=y",
    "UNXZ=y",
    "XZCAT=y",
    "UNLZMA=y",
    "LZCAT=y",
    "SHA256SUM=y",
    "MD5SUM=y",
    "FEATURE_HUMAN_READABLE=y",
    "FEATURE_LS_TIMESTAMPS=y",
    "FEATURE_LS_USERNAME=y",
    "FEATURE_LS_RECURSIVE=y",
    "FEATURE_FIND_TYPE=y",
    "FEATURE_FIND_EXEC=y",
    "FEATURE_SEAMLESS_GZ=y",
    "FEATURE_SEAMLESS_BZ2=y",
    "FEATURE_SEAMLESS_XZ=y",
    "FEATURE_TAR_CREATE=y",
    "FEATURE_TAR_AUTODETECT=y",
    "FEATURE_TAR_LONG_OPTIONS=y",
    "FEATURE_AWK_GNU_EXTENSIONS=y",
    "FEATURE_FANCY_HEAD=y",
    "FEATURE_FANCY_TAIL=y",
    "FEATURE_CATN=y",
    "FEATURE_CATV=y",
)


@dataclass(frozen=True)
class Profile:
    name: str
    title: str
    config_target: str
    symbols: tuple[str, ...]
    run_tests: bool


PROFILES = (
    Profile(
        name="allnoconfig-minimal",
        title="allnoconfig minimal C-only",
        config_target="allnoconfig",
        symbols=("BUSYBOX=y", "FEATURE_RUST_APPLETS=n"),
        run_tests=True,
    ),
    Profile(
        name="defconfig",
        title="defconfig C-only",
        config_target="defconfig",
        symbols=("FEATURE_RUST_APPLETS=n",),
        run_tests=True,
    ),
    Profile(
        name="feature-rich",
        title="curated feature-rich C-only",
        config_target="allnoconfig",
        symbols=FEATURE_RICH_SYMBOLS,
        run_tests=True,
    ),
)


@dataclass
class CommandResult:
    returncode: int
    log: Path


@dataclass
class BaselineResult:
    profile: Profile
    source_dir: Path
    build: CommandResult
    tests: CommandResult | None
    size_table: str
    busybox_bytes: int
    busybox_unstripped_bytes: int
    applets: list[str]
    enabled_symbols: list[str]
    link_map: Path | None


def ignored(_dir: str, names: list[str]) -> set[str]:
    ignored_names: set[str] = set()
    for name in names:
        rel = name
        if rel in COPY_EXCLUDED_DIRS or rel.startswith(".kernelrelease"):
            ignored_names.add(name)
    return ignored_names


def copy_source(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(REPO_ROOT, target, ignore=ignored)


def run_command(
    args: list[str],
    cwd: Path,
    log: Path,
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> CommandResult:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as output:
        proc = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if check and proc.returncode != 0:
        raise RuntimeError(f"{args!r} failed with {proc.returncode}; see {log}")
    return CommandResult(proc.returncode, log)


def set_config(source_dir: Path, assignments: tuple[str, ...]) -> None:
    if assignments:
        run_command(
            ["python3", "scripts/ci_set_config.py", *assignments],
            cwd=source_dir,
            log=source_dir / "baseline-logs" / "set-config.log",
        )


def command_output(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True)


def enabled_symbols(config: Path) -> list[str]:
    return sorted(
        line.split("=", 1)[0][len("CONFIG_") :]
        for line in config.read_text().splitlines()
        if line.startswith("CONFIG_") and line.endswith("=y")
    )


def collect_known_skips() -> tuple[list[str], list[str]]:
    known = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "testsuite").rglob("*")
        if path.is_file() and "SKIP_KNOWN_BUGS" in path.read_text(errors="ignore")
    )
    internet = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "testsuite").rglob("*")
        if path.is_file() and "SKIP_INTERNET_TESTS" in path.read_text(errors="ignore")
    )
    return known, internet


def build_profile(profile: Profile, build_dir: Path, jobs: int) -> BaselineResult:
    source_dir = build_dir / profile.name / "src"
    copy_source(source_dir)
    logs = source_dir / "baseline-logs"

    run_command(["make", profile.config_target], cwd=source_dir, log=logs / "config.log")
    set_config(source_dir, profile.symbols)
    run_command(
        ["sh", "-c", "yes '' | make oldconfig"],
        cwd=source_dir,
        log=logs / "oldconfig.log",
        env={**os.environ, "KCONFIG_NOTIMESTAMP": "1"},
    )
    build = run_command(
        [
            "make",
            f"-j{jobs}",
            "busybox",
            "EXTRA_LDFLAGS=-Wl,-Map,busybox.map",
        ],
        cwd=source_dir,
        log=logs / "build.log",
    )

    tests: CommandResult | None = None
    if profile.run_tests:
        test_env = {
            **os.environ,
            "SKIP_KNOWN_BUGS": "1",
            "SKIP_INTERNET_TESTS": "1",
        }
        tests = run_command(
            ["./runtest"],
            cwd=source_dir / "testsuite",
            log=logs / "runtest.log",
            env=test_env,
            check=False,
        )

    size_table = command_output(["size", "busybox", "busybox_unstripped"], cwd=source_dir).strip()
    applets = command_output(["./busybox", "--list"], cwd=source_dir).splitlines()
    (logs / "applets.list").write_text("\n".join(applets) + "\n")
    symbols = enabled_symbols(source_dir / ".config")
    (logs / "enabled-config-symbols.list").write_text("\n".join(symbols) + "\n")

    link_map = source_dir / "busybox.map"
    return BaselineResult(
        profile=profile,
        source_dir=source_dir,
        build=build,
        tests=tests,
        size_table=size_table,
        busybox_bytes=(source_dir / "busybox").stat().st_size,
        busybox_unstripped_bytes=(source_dir / "busybox_unstripped").stat().st_size,
        applets=applets,
        enabled_symbols=symbols,
        link_map=link_map if link_map.exists() else None,
    )


def fail_lines(log: Path) -> list[str]:
    if not log.exists():
        return []
    return [line for line in log.read_text(errors="ignore").splitlines() if line.startswith("FAIL:")]


def details_block(summary: str, lines: list[str]) -> str:
    body = "\n".join(lines) if lines else "(none)"
    return f"<details><summary>{summary}</summary>\n\n```text\n{body}\n```\n\n</details>"


def render_report(results: list[BaselineResult]) -> str:
    known_skip_files, internet_skip_files = collect_known_skips()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# C-only BusyBox baseline",
        "",
        "This document records the reproducible C-only baseline for the Rust",
        "migration. The baseline is generated by `scripts/c_only_baseline_report.py`",
        "and should be refreshed when build behavior, tests, or size baselines",
        "change materially.",
        "",
        f"Generated: {now}.",
        "",
        "## Reproduce",
        "",
        "Use the Docker wrapper so host toolchain differences do not affect the",
        "baseline:",
        "",
        "```sh",
        "sh scripts/docker-c-only-baseline-report.sh --output docs/c-only-baseline.md",
        "```",
        "",
        "The script builds isolated source copies under `build/c-only-baseline/`.",
        "Each profile records its build log, `testsuite/runtest` log, applet list,",
        "enabled config symbols, binary size, and linker map.",
        "",
        "## Profiles",
        "",
        "| profile | config source | build | testsuite | applets | enabled config symbols | busybox bytes | busybox_unstripped bytes | link map |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        test_cell = "not run"
        if result.tests is not None:
            test_cell = "pass" if result.tests.returncode == 0 else f"fail ({result.tests.returncode})"
        link_cell = "present" if result.link_map else "missing"
        lines.append(
            "| "
            f"{result.profile.name} | "
            f"`make {result.profile.config_target}` + overrides | "
            f"{'pass' if result.build.returncode == 0 else 'fail'} | "
            f"{test_cell} | "
            f"{len(result.applets)} | "
            f"{len(result.enabled_symbols)} | "
            f"{result.busybox_bytes} | "
            f"{result.busybox_unstripped_bytes} | "
            f"{link_cell} |"
        )
    lines.extend(
        [
            "",
            "## Binary size",
            "",
        ]
    )
    for result in results:
        lines.extend(
            [
                f"### {result.profile.title}",
                "",
                "```text",
                result.size_table,
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## Testsuite baseline",
            "",
            "`testsuite/runtest` is run with `SKIP_KNOWN_BUGS=1` and",
            "`SKIP_INTERNET_TESTS=1`. Failures in that mode are recorded as",
            "current baseline failures for this snapshot. Future runs should compare",
            "against this list; failures not listed here are new regressions.",
            "Tests gated by those variables are tracked separately below as",
            "known or environment-dependent skips.",
            "",
            "| profile | result | baseline failure count | log |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for result in results:
        if result.tests is None:
            lines.append(f"| {result.profile.name} | not run | 0 | n/a |")
            continue
        failures = fail_lines(result.tests.log)
        outcome = "pass" if result.tests.returncode == 0 else f"fail ({result.tests.returncode})"
        rel_log = result.tests.log.relative_to(REPO_ROOT)
        lines.append(f"| {result.profile.name} | {outcome} | {len(failures)} | `{rel_log}` |")

    for result in results:
        if result.tests is None:
            continue
        failures = fail_lines(result.tests.log)
        if failures:
            lines.extend(
                [
                    "",
                    f"### Baseline failures: {result.profile.name}",
                    "",
                    "```text",
                    *failures,
                    "```",
                ]
            )

    lines.extend(
        [
            "",
            "## Known skipped tests",
            "",
            "These files contain tests that are intentionally skipped when the",
            "baseline is run with `SKIP_KNOWN_BUGS=1`:",
            "",
            details_block("Known-bug-gated test files", known_skip_files),
            "",
            "These files contain tests that require network access and are skipped",
            "with `SKIP_INTERNET_TESTS=1`:",
            "",
            details_block("Internet-gated test files", internet_skip_files),
            "",
            "## Enabled applets",
            "",
        ]
    )
    for result in results:
        lines.extend(
            [
                details_block(
                    f"{result.profile.name}: {len(result.applets)} applets",
                    result.applets,
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Build artifacts",
            "",
            "The generated build directories are intentionally not committed. Re-run",
            "the script to recreate them. For each profile, the important artifacts",
            "are:",
            "",
            "- `baseline-logs/build.log`: compiler and linker output.",
            "- `baseline-logs/runtest.log`: full testsuite output.",
            "- `baseline-logs/applets.list`: enabled applets from `busybox --list`.",
            "- `baseline-logs/enabled-config-symbols.list`: enabled `.config` symbols.",
            "- `busybox.map`: linker map generated with `-Wl,-Map,busybox.map`.",
            "",
            "## Maintenance",
            "",
            "- Refresh this document with the Docker wrapper before changing the Rust",
            "  migration baseline.",
            "- Keep known skipped tests separate from unexpected failures.",
            "- Do not compare Rust applet size deltas against this document; use",
            "  `scripts/rust_size_report.py` for C-vs-Rust applet size deltas.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)

    build_dir = args.build_dir
    build_dir.mkdir(parents=True, exist_ok=True)
    results = [build_profile(profile, build_dir, args.jobs) for profile in PROFILES]
    report = render_report(results)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
