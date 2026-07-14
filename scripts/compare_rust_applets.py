#!/usr/bin/env python3
"""Compare BusyBox C applets with their opt-in Rust implementations."""

from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import subprocess
import shutil
import sys
from dataclasses import dataclass


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD_DIR = REPO_ROOT / "build" / "rust-compare"
APPLETS = {
    "basename": "BASENAME",
    "cat": "CAT",
    "dirname": "DIRNAME",
    "false": "FALSE",
    "pwd": "PWD",
    "true": "TRUE",
}
COPY_EXCLUDED_DIRS = {
    ".git",
    "build",
    "__pycache__",
    "target",
}


@dataclass(frozen=True)
class Case:
    applet: str
    name: str
    args: tuple[str, ...] = ()
    symlink: bool = False
    stdin: bytes | None = None
    broken_pipe: bool = False


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: bytes
    stderr: bytes


def run_command(
    argv: list[str],
    *,
    cwd: Path = REPO_ROOT,
    input_text: str | None = None,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            input=input_text,
            text=True,
            check=True,
            capture_output=quiet,
        )
    except subprocess.CalledProcessError as error:
        if quiet:
            if error.stdout:
                sys.stderr.write(error.stdout)
            if error.stderr:
                sys.stderr.write(error.stderr)
        raise


def tracked_files() -> list[Path]:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        if completed.returncode == 0:
            names = completed.stdout.decode().split("\0")
            return [Path(name) for name in names if name]
    except FileNotFoundError:
        pass

    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        relative_path = path.relative_to(REPO_ROOT)
        if not path.is_file():
            continue
        if COPY_EXCLUDED_DIRS.intersection(relative_path.parts):
            continue
        files.append(relative_path)
    return files


def copy_source_tree(destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True)

    for relative_path in tracked_files():
        source = REPO_ROOT / relative_path
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def set_config(config: Path, assignments: list[str]) -> None:
    run_command(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "ci_set_config.py"),
            "--config",
            str(config),
            *assignments,
        ]
    )


def configure_busybox(
    source_dir: Path,
    applets: list[str],
    *,
    rust: bool,
    quiet: bool = False,
) -> Path:
    copy_source_tree(source_dir)
    run_command(["make", "allnoconfig"], cwd=source_dir, quiet=quiet)

    assignments = ["BUSYBOX=y"]
    assignments.extend(f"{APPLETS[applet]}=y" for applet in applets)
    assignments.append(f"FEATURE_RUST_APPLETS={'y' if rust else 'n'}")
    set_config(source_dir / ".config", assignments)

    run_command(["make", "oldconfig"], cwd=source_dir, input_text="\n" * 512, quiet=quiet)
    run_command(["make", "busybox"], cwd=source_dir, quiet=quiet)
    return source_dir / "busybox"


def build_binaries(
    build_dir: Path,
    applets: list[str],
    *,
    quiet: bool = False,
) -> tuple[Path, Path]:
    c_busybox = configure_busybox(build_dir / "c-src", applets, rust=False, quiet=quiet)
    rust_busybox = configure_busybox(build_dir / "rust-src", applets, rust=True, quiet=quiet)
    return c_busybox, rust_busybox


def applet_cases(applets: list[str]) -> list[Case]:
    cases: list[Case] = []
    for applet in applets:
        if applet in {"false", "true"}:
            cases.append(Case(applet=applet, name="direct"))
            cases.append(Case(applet=applet, name="direct-with-arg", args=("ignored",)))
            cases.append(Case(applet=applet, name="symlink", symlink=True))
        elif applet == "basename":
            cases.extend(
                [
                    Case(applet=applet, name="plain", args=("/usr/local/bin/foo",)),
                    Case(applet=applet, name="trailing-slash", args=("/usr/local/bin/",)),
                    Case(applet=applet, name="root", args=("/",)),
                    Case(applet=applet, name="suffix", args=("/foo/bar.txt", ".txt")),
                    Case(applet=applet, name="suffix-not-whole", args=("foo", "foo")),
                    Case(applet=applet, name="dash-dash", args=("--", "/tmp/foo")),
                    Case(applet=applet, name="all", args=("-a", "/a/b", "/c/d/")),
                    Case(applet=applet, name="suffix-option", args=("-s", ".txt", "/a/b.txt", "c.txt")),
                    Case(applet=applet, name="symlink", args=("/usr/bin/test",), symlink=True),
                ]
            )
        elif applet == "dirname":
            cases.extend(
                [
                    Case(applet=applet, name="plain", args=("/tmp/foo",)),
                    Case(applet=applet, name="trailing-slash", args=("/tmp/foo/",)),
                    Case(applet=applet, name="relative", args=("foo",)),
                    Case(applet=applet, name="root", args=("/",)),
                    Case(applet=applet, name="dash-dash", args=("--", "/tmp/foo")),
                    Case(applet=applet, name="symlink", args=("/tmp/foo",), symlink=True),
                ]
            )
        elif applet == "pwd":
            cases.append(Case(applet=applet, name="direct"))
            cases.append(Case(applet=applet, name="symlink", symlink=True))
        elif applet == "cat":
            cases.extend(
                [
                    Case(applet=applet, name="stdin", stdin=b"from stdin\n"),
                    Case(applet=applet, name="one-file", args=("one",)),
                    Case(applet=applet, name="multiple-files", args=("one", "two")),
                    Case(applet=applet, name="file-and-stdin", args=("one", "-"), stdin=b"tail\n"),
                    Case(applet=applet, name="missing", args=("missing",)),
                    Case(applet=applet, name="broken-pipe", args=("large",), broken_pipe=True),
                    Case(applet=applet, name="symlink", args=("one",), symlink=True),
                ]
            )
    return cases


def run_case(binary: Path, case: Case, link_dir: Path) -> Result:
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    if case.symlink:
        link = link_dir / case.applet
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(binary)
        argv = [str(link), *case.args]
    else:
        argv = [str(binary), case.applet, *case.args]

    if case.broken_pipe:
        read_fd, write_fd = os.pipe()
        process = subprocess.Popen(
            argv,
            cwd=link_dir,
            env=env,
            stdin=subprocess.PIPE if case.stdin is not None else subprocess.DEVNULL,
            stdout=write_fd,
            stderr=subprocess.PIPE,
        )
        os.close(write_fd)
        os.close(read_fd)
        _, stderr = process.communicate(case.stdin)
        return Result(process.returncode, b"", stderr)

    completed = subprocess.run(
        argv, cwd=link_dir, env=env, input=case.stdin, capture_output=True, check=False
    )
    return Result(completed.returncode, completed.stdout, completed.stderr)


def text_diff(label: str, c_bytes: bytes, rust_bytes: bytes) -> list[str]:
    c_text = c_bytes.decode("utf-8", "replace").splitlines(keepends=True)
    rust_text = rust_bytes.decode("utf-8", "replace").splitlines(keepends=True)
    return list(
        difflib.unified_diff(
            c_text,
            rust_text,
            fromfile=f"c/{label}",
            tofile=f"rust/{label}",
        )
    )


def compare_case(c_binary: Path, rust_binary: Path, case: Case, tmp_dir: Path) -> list[str]:
    c_result = run_case(c_binary, case, tmp_dir / "c-links")
    rust_result = run_case(rust_binary, case, tmp_dir / "rust-links")

    failures: list[str] = []
    if c_result.returncode != rust_result.returncode:
        failures.append(
            f"exit code differs: c={c_result.returncode} rust={rust_result.returncode}"
        )
    if c_result.stdout != rust_result.stdout:
        failures.append("stdout differs:")
        failures.extend(
            line.rstrip("\n")
            for line in text_diff("stdout", c_result.stdout, rust_result.stdout)
        )
    if c_result.stderr != rust_result.stderr:
        failures.append("stderr differs:")
        failures.extend(
            line.rstrip("\n")
            for line in text_diff("stderr", c_result.stderr, rust_result.stderr)
        )
    return failures


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and compare BusyBox C applets against Rust applet builds."
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=DEFAULT_BUILD_DIR,
        help=f"out-of-tree build directory (default: {DEFAULT_BUILD_DIR})",
    )
    parser.add_argument("--c-busybox", type=Path, help="existing C BusyBox binary")
    parser.add_argument("--rust-busybox", type=Path, help="existing Rust BusyBox binary")
    parser.add_argument(
        "--applet",
        action="append",
        choices=sorted(APPLETS),
        help="applet to compare; may be passed multiple times",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    applets = args.applet or sorted(APPLETS)

    if bool(args.c_busybox) != bool(args.rust_busybox):
        raise SystemExit("--c-busybox and --rust-busybox must be provided together")
    if args.c_busybox and args.rust_busybox:
        c_binary = args.c_busybox.resolve()
        rust_binary = args.rust_busybox.resolve()
    else:
        c_binary, rust_binary = build_binaries(args.build_dir, applets)

    tmp_dir = args.build_dir / "run"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    (tmp_dir / "c-links").mkdir(parents=True)
    (tmp_dir / "rust-links").mkdir(parents=True)
    for directory in (tmp_dir / "c-links", tmp_dir / "rust-links"):
        (directory / "one").write_bytes(b"first\n")
        (directory / "two").write_bytes(b"second\n")
        (directory / "large").write_bytes(b"x" * (1024 * 1024))

    failures = 0
    for case in applet_cases(applets):
        case_failures = compare_case(c_binary, rust_binary, case, tmp_dir)
        label = f"{case.applet} {case.name} args={list(case.args)!r}"
        if case_failures:
            failures += 1
            print(f"FAIL {label}")
            for failure in case_failures:
                print(f"  {failure}")
        else:
            print(f"PASS {label}")

    if failures:
        print(f"{failures} comparison case(s) failed", file=sys.stderr)
        return 1
    print(f"{len(applet_cases(applets))} comparison case(s) passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
