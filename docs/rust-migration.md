# Rust migration

This document defines the first migration rules for introducing Rust into this
BusyBox tree. The migration is incremental: the existing C build, Kconfig,
Kbuild, applet metadata generation, and testsuite remain authoritative until a
specific area is explicitly migrated.

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

## Applet ABI

Rust applets must expose a C-compatible entry point matching the BusyBox applet
dispatcher shape:

```c
int <applet>_main(int argc, char **argv);
```

Rust implementations should use `busybox_rs::ffi::run_applet` or an equivalent
wrapper so argument validation and future panic handling stay centralized.

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
