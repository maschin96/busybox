use core::ffi::{c_char, c_int};
use core::ptr::NonNull;

/// Raw BusyBox applet arguments received from the C dispatcher.
///
/// This type deliberately keeps conversion narrow. Applet implementations can
/// decide whether an argument must be valid UTF-8, lossily printable, or an
/// opaque byte string passed through to libc.
#[derive(Clone, Copy)]
pub struct RawArgv {
    argc: c_int,
    argv: NonNull<*mut c_char>,
}

impl RawArgv {
    /// Create a checked view over C `argc`/`argv`.
    ///
    /// # Safety
    ///
    /// `argv` must point to an array of at least `argc` pointers for the
    /// duration of the applet call. Each non-null element must be a valid
    /// NUL-terminated C string if it is later read as a string.
    pub unsafe fn new(argc: c_int, argv: *mut *mut c_char) -> Option<Self> {
        if argc < 0 {
            return None;
        }
        Some(Self {
            argc,
            argv: NonNull::new(argv)?,
        })
    }

    pub fn argc(self) -> c_int {
        self.argc
    }

    pub fn is_empty(self) -> bool {
        self.argc == 0
    }

    pub fn as_ptr(self) -> *mut *mut c_char {
        self.argv.as_ptr()
    }
}

/// Return code used when Rust receives invalid applet arguments from C.
pub const APPLET_USAGE_ERROR: c_int = 1;

/// Convert a Rust applet body into a C-compatible BusyBox applet entry point.
///
/// Panics must not unwind across the C boundary. This helper is intentionally
/// small until the migration decides on a repo-wide panic policy.
///
/// # Safety
///
/// `argv` must follow BusyBox's normal applet ABI: it points to an array of at
/// least `argc` C string pointers for the duration of the call.
pub unsafe fn run_applet(
    argc: c_int,
    argv: *mut *mut c_char,
    body: impl FnOnce(RawArgv) -> c_int,
) -> c_int {
    // SAFETY: The C dispatcher is expected to provide BusyBox's normal
    // argc/argv pair. Invalid null/negative inputs are rejected here.
    let Some(raw_argv) = (unsafe { RawArgv::new(argc, argv) }) else {
        return APPLET_USAGE_ERROR;
    };
    body(raw_argv)
}
