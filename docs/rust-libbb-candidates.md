# Rust replacements for simple libbb utilities

This evaluation covers utilities that can be replaced with reviewable Rust
without touching applet dispatch, signal/fork/exec paths, global buffers, or
assembler-specific implementations.

| priority | candidate | risk | current evidence | decision |
| --- | --- | --- | --- | --- |
| 1 | byte-oriented path operations | low | basename/dirname cases, path FFI ownership tests, C-vs-Rust harness | migrate individual pure transforms first |
| 2 | fixed output composition | low | `full_write`, Cat copy, Broken Pipe, yes/path/stdout applet comparisons | share small Rust helpers; keep FD syscalls in libbb bridge |
| 3 | bounded integer parsing | medium | mature C parsers, but no dedicated cross-language edge corpus yet | prototype only after differential tests cover signs, bases, overflow, suffixes, errno, and ranges |
| 4 | CRC/hash code without assembler | medium-high | existing C implementations and size tooling; no vector/performance gate for Rust | defer until vectors, endian targets, size, and throughput baselines exist |

## Boundaries

Path and output helpers operate on byte slices, not UTF-8 strings. Allocation,
diagnostics, descriptors, and process-global state stay behind the fixed C ABI.
The existing `concat_path_file`, current-directory ownership, `full_write`, and
copy-to-stdout wrappers are interoperability boundaries, not candidates for a
second syscall implementation in Rust.

The first genuine shared Rust extraction should be the already exercised pure
path-component and suffix logic. It has deterministic inputs, no libc ABI, and
strong differential coverage. Output composition may follow once two applets
need the same byte-line helper.

Number parsing is deceptively compatibility-sensitive. A prototype must run
the same table against the C parser and Rust implementation and compare value,
accepted prefix, diagnostic, and exit behavior. It must not replace xfunc
parsers that intentionally terminate until that behavior is modeled.

CRC/hash migration is not approved by this evaluation. It first needs known
answer tests, unaligned-buffer cases, multiple architectures/endianness, and
size/throughput thresholds. Hardware-accelerated and assembler paths remain C.
