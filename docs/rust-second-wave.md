# Second Rust applet wave

The second wave is ordered by behavioral risk, current implementation size,
test readiness, and required FFI surface. Source line counts are a rough
complexity signal from the 2026-07-14 tree, not a size target.

| order | applet | C lines | dedicated tests found | risk | prerequisite |
| --- | --- | ---: | ---: | --- | --- |
| 1 | `printenv` | 59 | 0 | low-medium | byte-oriented environment comparison cases |
| 2 | `unlink` | 33 | 0 | low-medium | fixed unlink/error FFI and filesystem cases |
| 3 | `tty` | 66 | 0 | medium | PTY/non-PTY harness and exact exit-code checks |
| 4 | `rmdir` | 95 | 1 file | medium | expand empty/nonempty/parents/error cases |

These four applets form the concrete second wave. Each applet remains a normal
applet on its Rust path until its NOFORK/NOEXEC review passes independently.

## Sequencing

1. Add C-baseline cases before each port. Missing tests are a gate, not an
   argument to assume simple behavior.
2. Port `printenv` without UTF-8 conversion. Cover empty environments, missing
   names, multiple variables, ordering, bytes, stdout failure, and exit status.
3. Port `unlink` through a fixed libbb bridge so errno diagnostics remain
   BusyBox-compatible. Cover missing operands, extra operands, files,
   directories, permissions, and missing paths.
4. Extend the harness with a real pseudo-terminal before `tty`. Cover normal
   stdin, PTY stdin, `-s` when enabled, ignored arguments, and exit codes 0/1/2.
5. Port `rmdir` after its filesystem matrix covers empty/nonempty directories,
   `-p`, verbose mode when configured, missing parents, and partial failure.

After every step, run the C-vs-Rust direct and symlink cases, Rust unit tests,
the Rust-enabled BusyBox link, and the binary-size report. A regression or
unexplained size jump stops the wave before the next applet.

## Deferred candidates

| applet | C lines | reason to defer | unblock condition |
| --- | ---: | --- | --- |
| `echo` | 351 | dense escape, option, shell-builtin, and feature-flag semantics | dedicated differential corpus for fancy/plain modes and NUL/escape bytes |
| `sync` | 140 | persistent side effects, multiple syscall modes, weak tests | isolated filesystem test environment and sync/fsync/fdatasync failure injection |
| `sleep` | 103 | shared duration parsing, fractional values, signals, and timing flakiness | parser differential tests plus bounded monotonic timing tests |

The next planning checkpoint occurs after all four selected applets have size
and behavior evidence. Deferred applets are reconsidered then; they are not
implicitly part of this wave.
