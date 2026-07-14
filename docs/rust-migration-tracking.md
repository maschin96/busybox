# Rust migration tracking

This document is the durable tracking artifact for the BusyBox Rust migration.
It records the current order, dependencies, issue status, milestones, and first
applet wave so the GitHub issue list is not the only source of migration state.

Status snapshot: 2026-07-14.

## Goals

- Keep the C-only BusyBox build working throughout the migration.
- Migrate applets in small, reversible slices behind `FEATURE_RUST_APPLETS`.
- Keep every migration step tied to a GitHub issue, comparison evidence, and
  size evidence where applicable.
- Prefer low-risk coreutils applets until the Rust ABI, build, testing, and
  FFI rules are stable enough for broader work.

## Milestones

### M0: Migration foundation

Purpose: establish the Rust workspace, policy, ABI, safety rules, and guardrails
needed before applets can be migrated.

Required issues:

- [#1 Applet-Metadaten-Strategie fuer Rust festlegen](https://github.com/maschin96/RustyBox/issues/1) - closed
- [#2 Cargo-Workspace fuer BusyBox-Rust-Code anlegen](https://github.com/maschin96/RustyBox/issues/2) - closed
- [#3 Tracking: Rust-Migration fuer BusyBox planen und steuern](https://github.com/maschin96/RustyBox/issues/3) - closed by this tracking document
- [#5 Safety-Regeln fuer FFI und libc-Zugriffe definieren](https://github.com/maschin96/RustyBox/issues/5) - closed
- [#6 Rust-Toolchain-Policy festlegen](https://github.com/maschin96/RustyBox/issues/6) - closed
- [#7 C-ABI-Konvention fuer Rust-Applets definieren](https://github.com/maschin96/RustyBox/issues/7) - closed
- [#16 NOFORK- und NOEXEC-Regeln fuer Rust-Applets klaeren](https://github.com/maschin96/RustyBox/issues/16) - closed
- [#19 High-Risk-Komponenten explizit zurueckstellen](https://github.com/maschin96/RustyBox/issues/19) - closed
- [#21 Lizenz- und Dependency-Policy fuer Rust-Crates festlegen](https://github.com/maschin96/RustyBox/issues/21) - closed

Exit state: complete.

### M1: First applet wave

Purpose: validate opt-in Rust applets with low-risk behavior before moving to
broader I/O and libbb-heavy applets.

First-wave applets, in order:

1. `true` - [#11](https://github.com/maschin96/RustyBox/issues/11), closed.
2. `false` - [#13](https://github.com/maschin96/RustyBox/issues/13), closed.
3. `basename`, `dirname`, `pwd` - [#9](https://github.com/maschin96/RustyBox/issues/9), closed.
4. `cat` - [#12](https://github.com/maschin96/RustyBox/issues/12), complete.
5. `yes`, `whoami`, `hostid` - [#14](https://github.com/maschin96/RustyBox/issues/14), complete.

Supporting first-wave issues:

- [#15 Vergleichstest-Harness fuer C-vs-Rust-Applets bauen](https://github.com/maschin96/RustyBox/issues/15) - closed.
- [#10 Binary-Size-Reporting fuer Rust-Applets einfuehren](https://github.com/maschin96/RustyBox/issues/10) - closed.
- [#22 libbb-FFI-Bruecke fuer Rust-Applets definieren](https://github.com/maschin96/RustyBox/issues/22) - closed.

Exit state: complete.

### M2: Build and target coverage

Purpose: make the Rust path reproducible beyond the current native CI flow.

Required issues:

- [#4 Baseline fuer Build, Tests und Binary-Groesse erfassen](https://github.com/maschin96/RustyBox/issues/4) - closed by `docs/c-only-baseline.md`.
- [#8 Kbuild-Integration fuer Rust-Static-Library planen](https://github.com/maschin96/RustyBox/issues/8) - complete; design recorded in `docs/rust-kbuild-integration.md`.
- [#17 Cross-Compile-Support fuer Rust validieren](https://github.com/maschin96/RustyBox/issues/17) - complete; matrix in `docs/rust-cross-compile.md`.

Exit state: complete.

### M3: Candidate expansion

Purpose: choose the next low-risk work based on the evidence gathered from the
first applet wave.

Required issues:

- [#18 Rust-Ersatz fuer einfache libbb-Utilities evaluieren](https://github.com/maschin96/RustyBox/issues/18) - complete; evaluation in `docs/rust-libbb-candidates.md`.
- [#20 Zweite Applet-Welle planen](https://github.com/maschin96/RustyBox/issues/20) - complete; plan in `docs/rust-second-wave.md`.

Exit state: complete.

## Issue order and dependencies

| issue | status | milestone | depends on | unblocks |
| --- | --- | --- | --- | --- |
| [#1 Applet metadata strategy](https://github.com/maschin96/RustyBox/issues/1) | closed | M0 | none | #8, applet shims |
| [#2 Cargo workspace](https://github.com/maschin96/RustyBox/issues/2) | closed | M0 | none | #7, #11, Rust CI |
| [#3 Migration tracking](https://github.com/maschin96/RustyBox/issues/3) | closed by this tracking document | M0 | issue inventory | milestone tracking |
| [#4 Baseline capture](https://github.com/maschin96/RustyBox/issues/4) | closed by `docs/c-only-baseline.md` | M2 | #10 recommended | #17, #20 |
| [#5 FFI and libc safety rules](https://github.com/maschin96/RustyBox/issues/5) | closed | M0 | #2 | #7, #22 |
| [#6 Toolchain policy](https://github.com/maschin96/RustyBox/issues/6) | closed | M0 | #2 | CI, #17 |
| [#7 C ABI convention](https://github.com/maschin96/RustyBox/issues/7) | closed | M0 | #2, #5 | #11, #13, applet ports |
| [#8 Kbuild integration plan](https://github.com/maschin96/RustyBox/issues/8) | complete | M2 | #1, #2, #6, #7 | stronger native build integration |
| [#9 Path applets](https://github.com/maschin96/RustyBox/issues/9) | closed | M1 | #7, #15 | path behavior evidence, #20 |
| [#10 Size reporting](https://github.com/maschin96/RustyBox/issues/10) | closed | M1 | #15 | #4, #20 |
| [#11 `true`](https://github.com/maschin96/RustyBox/issues/11) | closed | M1 | #7 | #13, CI smoke baseline |
| [#12 `cat`](https://github.com/maschin96/RustyBox/issues/12) | complete | M1 | #15, #22 | FD and broken-pipe evidence |
| [#13 `false`](https://github.com/maschin96/RustyBox/issues/13) | closed | M1 | #7, #11 | error-path baseline |
| [#14 stdout applets](https://github.com/maschin96/RustyBox/issues/14) | complete | M1 | #15, #22 | broader simple-output evidence |
| [#15 C-vs-Rust comparison harness](https://github.com/maschin96/RustyBox/issues/15) | closed | M1 | #11, #13 | #9, #10, #12, #14 |
| [#16 NOFORK/NOEXEC rules](https://github.com/maschin96/RustyBox/issues/16) | closed | M0 | #5, #7 | applet registration decisions |
| [#17 Cross-compile validation](https://github.com/maschin96/RustyBox/issues/17) | complete | M2 | #6, #8, #4 | target support matrix |
| [#18 libbb-like Rust utility candidates](https://github.com/maschin96/RustyBox/issues/18) | complete | M3 | #9, #12, #14 | #20, future utility ports |
| [#19 High-risk exclusions](https://github.com/maschin96/RustyBox/issues/19) | closed | M0 | none | scope control |
| [#20 Second applet wave](https://github.com/maschin96/RustyBox/issues/20) | complete | M3 | #4, #9, #10, #12, #14, #18 | next migration batch |
| [#21 Dependency policy](https://github.com/maschin96/RustyBox/issues/21) | closed | M0 | #6 | future crate review |
| [#22 libbb FFI bridge](https://github.com/maschin96/RustyBox/issues/22) | closed | M1 | #5, #7 | #12, #14, future applets |

## Current next actions

1. Execute the second wave from `docs/rust-second-wave.md`, beginning with
   comparison tests for `printenv` and then `unlink`.

## Tracking maintenance rules

- Update this document when an issue changes migration order, dependencies, or
  milestone scope.
- Keep issue status accurate when a migration issue is closed.
- Do not mark an applet as first-wave complete until C-vs-Rust comparison and
  size reporting cover it.
- Keep high-risk components out of the first wave unless a later issue changes
  the scope with explicit evidence.
