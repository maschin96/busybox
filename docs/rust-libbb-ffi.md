# Rust libbb FFI bridge

The Rust libbb bridge is the only supported path for Rust applets to call
BusyBox utility code. It deliberately exposes a small C ABI instead of binding
`libbb.h` directly. This keeps BusyBox's optional `FAST_FUNC` calling
convention, C preprocessor details, and variadic error functions out of Rust.

The ABI declarations live in `include/rust_ffi.h`, their C forwarding
implementations live in `libbb/rust_ffi.c`, and safe Rust wrappers live in
`rust/busybox-rs/src/libbb.rs`. The C object is built only when
`FEATURE_RUST_APPLETS` is enabled.

## Initial API surface

| Rust wrapper | C bridge | libbb or libc operation | behavior |
| --- | --- | --- | --- |
| `error_msg` | `bb_rust_error_msg` | `bb_error_msg("%s", ...)` | Prints a fixed-string BusyBox diagnostic. |
| `perror_msg` | `bb_rust_perror_msg` | `bb_perror_msg("%s", ...)` | Prints a fixed-string diagnostic plus the current `errno` text. |
| `open_input` | `bb_rust_open_input` | `open_or_warn_stdin` | Opens a named input or borrows stdin for `-`; libbb prints open failures. |
| `InputFd::copy_to_stdout` | `bb_rust_copy_to_stdout` | `bb_copyfd_eof` | Copies input to stdout and preserves libbb read/write diagnostics. |
| `full_write` | `bb_rust_full_write` | `full_write` | Retries interrupted writes and reports failed or partial output. |
| `InputFd` drop | `bb_rust_close` | `close` | Closes named inputs exactly once and leaves borrowed stdin open. |
| `current_dir` | `bb_rust_getcwd_or_warn` | `xrealloc_getcwd_or_warn` | Returns an allocated physical current directory or a diagnosed failure. |
| `concat_path_file` | `bb_rust_concat_path_file` | `concat_path_file` | Joins paths with existing BusyBox semantics. |
| `LibbbString` drop | `bb_rust_free` | `free` | Returns C allocations to the C allocator. |

This first surface prioritizes the operations needed by file- and path-oriented
applets without turning all of libbb into a public Rust ABI. In particular,
xfunc-style allocation remains owned by C and is represented by
`LibbbString`; Rust must not construct a `String`, `CString`, or `Vec` directly
from a libbb allocation.

## Safety and ownership rules

- Rust applets use the safe functions and types in `busybox_rs::libbb`. The
  private raw declarations are boundary implementation details.
- The C bridge uses only fixed signatures and the normal platform C calling
  convention. Variadic libbb functions must be wrapped with a fixed format,
  rather than declared as variadic Rust FFI.
- `open_input` owns descriptors opened for named files. The `-` input borrows
  standard input. `InputFd` expresses and enforces that distinction on drop.
- `full_write` borrows its byte slice only for the duration of the call. A
  successful return means the entire slice was written; partial output remains
  distinguishable from a failure before any byte was written.
- `LibbbString` is the sole owner of its returned pointer and frees it through
  `bb_rust_free`. It exposes borrowed `CStr` and byte views only.
- `perror_msg` must be called immediately after the failed operation because
  intervening calls may change `errno`.
- C entry points require non-null, NUL-terminated string arguments unless the
  header and wrapper explicitly allow null. Safe wrappers establish these
  preconditions before crossing the ABI.

## Extending the bridge

Add a bridge function only when an applet needs it. Each addition must include:

1. a fixed-signature declaration in `include/rust_ffi.h`;
2. a narrow forwarding implementation in `libbb/rust_ffi.c`;
3. a safe wrapper that documents pointer validity, ownership, errors, and
   process-global effects;
4. tests for success, failure, and ownership behavior where applicable.

Functions that exit the process, mutate global applet state, expose borrowed
global storage, or require callbacks need an explicit design review rather than
a mechanical binding.

## Verification

The Rust unit tests provide test-only C ABI implementations and exercise the
safe wrappers, including named-file versus stdin ownership, failed and partial
writes, fixed-string diagnostics, path results, and C-side deallocation.
The migrated path applets write through `full_write`, and `pwd` obtains and
releases its current-directory string through the bridge, providing real
applet-level coverage of the ABI and ownership path.
The Rust-enabled BusyBox build verifies that the real C bridge and Rust static
library link together. The default C-only build verifies that the opt-in bridge
does not affect normal BusyBox builds.
