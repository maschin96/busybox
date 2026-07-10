#![deny(unsafe_op_in_unsafe_fn)]

//! Rust support library for incremental BusyBox applet migration.
//!
//! The C build remains authoritative. Rust applets are introduced behind a
//! C-compatible ABI and linked into BusyBox as a static library.

mod coreutils;
pub mod ffi;
