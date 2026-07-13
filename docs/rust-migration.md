# Rust migration

This document defines the first migration rules for introducing Rust into this
BusyBox tree. The migration is incremental: the existing C build, Kconfig,
Kbuild, applet metadata generation, and testsuite remain authoritative until a
specific area is explicitly migrated.

The current issue order, dependency map, milestones, and first applet wave are
tracked in [rust-migration-tracking.md](rust-migration-tracking.md).
The current C-only build, testsuite, size, link-map, and applet baseline is
recorded in [c-only-baseline.md](c-only-baseline.md).

This repository is also a study of how AI coding agents can help with a
careful reimplementation or language transition from C to Rust. Agent-assisted
changes are expected to be small, reviewable, and evidence-backed. The
interesting outcome is not only whether an applet can be rewritten in Rust, but
whether the process can preserve BusyBox behavior, size discipline, portability,
and maintainability while leaving a clear audit trail for human reviewers.

## Migration goals

- Keep the existing C implementation as the behavioral reference until a Rust
  implementation has been explicitly accepted.
- Use Rust first where the risk is low and the expected safety or
  maintainability benefit is easy to reason about.
- Make each migration reversible by keeping the C implementation available and
  selecting the Rust path only through configuration.
- Record enough context for reviewers to understand what was changed, how the
  agent arrived there, and which verification was performed.
- Avoid broad rewrites, dependency growth, or runtime behavior changes that are
  not required for the applet being migrated.

## Agent-assisted workflow

AI agents may be used to propose, implement, document, or test migration steps,
but the repository should remain understandable without relying on hidden agent
state. Each agent-assisted migration should leave durable project artifacts:

- A focused code change that maps to one applet or one supporting
  infrastructure concern.
- Documentation updates when migration rules, scope, assumptions, or known
  limitations change.
- Test or comparison evidence showing the Rust behavior against the C baseline.
- A short rationale in the commit or pull request explaining why the applet was
  chosen and what was intentionally left unchanged.

Agent output is not a substitute for review. Reviewers should treat generated
code like any other contribution and check ABI boundaries, error handling,
platform assumptions, size impact, licensing, and conformance with BusyBox
style.

## Toolchain policy

- The initial Rust toolchain is pinned in `rust-toolchain.toml`.
- The minimum supported Rust version is Rust 1.79.0 until a later issue changes
  it with evidence from supported targets.
- The initial profile uses `std`; `no_std` is a later target-specific decision,
  not a default requirement for the first applet wave.
- New Rust dependencies are not allowed by default. Any dependency must document
  GPL-2.0-only compatibility, target support, size impact, and vendoring needs.

## Workspace layout

- Rust code lives below `rust/`.
- `rust/busybox-rs` builds a static library intended to be linked into the
  existing BusyBox binary.
- The C build remains authoritative. Adding the workspace must not change C-only
  builds until Kbuild integration is intentionally added.
- Rust applets are currently opt-in through `FEATURE_RUST_APPLETS`. Default
  configurations continue to use the C implementations.

The workspace should stay small and purpose-built. It exists to support
BusyBox applet migration experiments, not to become a separate replacement
project with independent behavior or command-line semantics.

## Applet ABI

Rust applets must expose a C-compatible entry point matching the BusyBox applet
dispatcher shape:

```c
int <applet>_main(int argc, char **argv);
```

Rust implementations should use `busybox_rs::ffi::run_applet` or an equivalent
wrapper so argument validation and future panic handling stay centralized.
The Rust ABI functions are `unsafe extern "C"` because the C dispatcher owns
the validity of `argc` and `argv`.

Rules:

- Do not unwind across the C ABI boundary.
- Preserve BusyBox stdout, stderr, and exit-code behavior.
- Treat argv as byte-oriented input unless an applet explicitly requires UTF-8.
- Keep C shims as the source of `//applet:`, `//config:`, `//usage:`, and
  `//kbuild:` metadata until Rust metadata generation is implemented.

## FFI safety rules

- All direct C/libc calls must be behind small wrappers with documented safety
  invariants.
- `unsafe` is allowed only at boundary points: argv handling, libc calls,
  exported applet entry points, and calls into existing `libbb`.
- A Rust applet must not assume it can mutate process-global state unless the C
  applet already does so and tests cover the behavior.
- `NOFORK` and `NOEXEC` must not be enabled for a Rust applet until allocator,
  stdio, panic, and process-global-state behavior are reviewed for that applet.

## First-wave scope

The first implementation wave is limited to low-risk coreutils applets and
supporting infrastructure:

- `true`
- `false`
- simple stdout applets such as `yes`, `whoami`, and `hostid`
- path applets such as `basename`, `dirname`, and `pwd`
- `cat` only after file-descriptor and broken-pipe behavior are covered

High-risk components are explicitly out of scope for the first wave: `ash`,
`hush`, TLS, init, mount, mdev, networking, archive, and compression code.

Current status:

- `true` has an opt-in Rust implementation behind `FEATURE_RUST_APPLETS`.
  The Rust path is intentionally registered as a normal applet, not NOFORK.
- `false` has an opt-in Rust implementation behind `FEATURE_RUST_APPLETS`.
  The Rust path is intentionally registered as a normal applet, not NOFORK.
- `basename`, `dirname`, and `pwd` have opt-in Rust implementations behind
  `FEATURE_RUST_APPLETS`. The Rust paths are intentionally registered as normal
  applets, not NOFORK, while allocator, stdio, panic, and process-global-state
  behavior are still being reviewed.

## Verification expectations

Every Rust applet migration must compare the Rust behavior against the C
behavior for:

- `busybox <applet>` invocation
- symlink invocation
- stdout
- stderr
- exit code
- binary size impact

The existing testsuite remains the acceptance baseline. New comparison tooling
should be added before migrating applets with meaningful I/O behavior.

`scripts/compare_rust_applets.py` is the reusable C-vs-Rust comparison harness
for the first applet wave. By default it builds isolated C and Rust BusyBox
variants under `build/rust-compare/`, runs the currently ported Rust applets
(`true`, `false`, `basename`, `dirname`, and `pwd`) through direct
`busybox <applet>` dispatch and symlink dispatch, and compares stdout, stderr,
and exit code. The path applet cases cover trailing slashes, root paths,
`basename` suffix removal, multi-file options, and `--`, `dirname --`, relative
paths, and `pwd` output from the physical current directory. Differences are
printed with the applet, invocation shape, arguments, and unified stdout/stderr
diffs so the failing case can be rerun.

To compare existing binaries instead of rebuilding them:

```sh
python3 scripts/compare_rust_applets.py \
  --c-busybox /path/to/c/busybox \
  --rust-busybox /path/to/rust/busybox
```

Rust applet pull requests should also include a size report generated by
`scripts/rust_size_report.py`. The report builds matching C and Rust BusyBox
variants by default, records `size(1)` totals for `busybox` and
`busybox_unstripped`, records the Rust static archive byte size, and lists
`<applet>_main` / `rust_<applet>_main` symbol sizes for the ported applets.
This gives reviewers a reproducible baseline and delta without requiring a
link-map-specific workflow.

```sh
python3 scripts/rust_size_report.py
```

On hosts where the native toolchain differs from the Linux target, use the
container wrapper:

```sh
sh scripts/docker-rust-size-report.sh
```

For agent-assisted work, verification notes should be written so another
reviewer can repeat the important checks without reconstructing the agent's
private context. At minimum, record the configuration used, the commands run,
the observed result, and any known gaps.

## Documentation expectations

Documentation is part of the migration surface. When a Rust migration changes
policy, scope, build behavior, testing practice, or applet status, update this
file in the same change. When a user-facing behavior changes, update the normal
BusyBox documentation or usage text instead of documenting the difference only
as a Rust migration detail.

Keep the documentation in Markdown where possible so it remains easy to review
in code review tools and usable by both human contributors and AI agents.
