//! Safe wrappers around the small C ABI in `include/rust_ffi.h`.
//!
//! This module owns all direct calls from Rust into libbb. The C bridge has
//! fixed signatures and the platform C calling convention, so Rust applets do
//! not depend on BusyBox's `FAST_FUNC` convention or C variadic functions.

use core::ffi::{c_char, c_int, c_void};
use core::ptr::NonNull;
use std::ffi::CStr;
use std::os::fd::{AsRawFd, RawFd};

mod raw {
    use super::{c_char, c_int, c_void};

    extern "C" {
        pub fn bb_rust_error_msg(message: *const c_char);
        pub fn bb_rust_perror_msg(message: *const c_char);
        pub fn bb_rust_open_input(path: *const c_char) -> c_int;
        pub fn bb_rust_copy_to_stdout(fd: c_int) -> c_int;
        pub fn bb_rust_full_write(fd: c_int, buffer: *const c_void, length: usize) -> isize;
        pub fn bb_rust_close(fd: c_int) -> c_int;
        pub fn bb_rust_getcwd_or_warn() -> *mut c_char;
        pub fn bb_rust_concat_path_file(
            path: *const c_char,
            filename: *const c_char,
        ) -> *mut c_char;
        pub fn bb_rust_free(pointer: *mut c_void);
    }
}

/// Print a BusyBox-style error message without consulting `errno`.
pub fn error_msg(message: &CStr) {
    // SAFETY: `message` is NUL-terminated and remains alive for the call.
    unsafe { raw::bb_rust_error_msg(message.as_ptr()) }
}

/// Print a BusyBox-style error message followed by the current `errno` text.
///
/// Call this immediately after the failing operation so no intervening call
/// can replace `errno`.
pub fn perror_msg(message: &CStr) {
    // SAFETY: `message` is NUL-terminated and remains alive for the call.
    unsafe { raw::bb_rust_perror_msg(message.as_ptr()) }
}

/// Failure returned after `open_or_warn_stdin` has already printed a warning.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct OpenInputError;

/// An input descriptor opened by libbb.
///
/// Named files are closed on drop. `-` borrows standard input and is never
/// closed by this value.
#[derive(Debug)]
pub struct InputFd {
    fd: RawFd,
    owned: bool,
}

impl AsRawFd for InputFd {
    fn as_raw_fd(&self) -> RawFd {
        self.fd
    }
}

impl Drop for InputFd {
    fn drop(&mut self) {
        if self.owned {
            // SAFETY: An owned descriptor is closed exactly once here.
            let _ = unsafe { raw::bb_rust_close(self.fd) };
        }
    }
}

impl InputFd {
    /// Copy this input to standard output using libbb's diagnosed copy loop.
    pub fn copy_to_stdout(&self) -> Result<(), CopyError> {
        // SAFETY: `self` owns or borrows a valid descriptor for this call.
        if unsafe { raw::bb_rust_copy_to_stdout(self.fd) } < 0 {
            Err(CopyError)
        } else {
            Ok(())
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CopyError;

/// Open a path for reading, treating `-` as borrowed standard input.
///
/// libbb prints the diagnostic before an error is returned.
pub fn open_input(path: &CStr) -> Result<InputFd, OpenInputError> {
    // SAFETY: `path` is NUL-terminated and remains alive for the call.
    let fd = unsafe { raw::bb_rust_open_input(path.as_ptr()) };
    if fd < 0 {
        return Err(OpenInputError);
    }
    Ok(InputFd {
        fd,
        owned: path.to_bytes() != b"-",
    })
}

/// Failure from a libbb `full_write` operation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WriteError {
    /// Nothing was written and the underlying write failed.
    Failed,
    /// Some, but not all, bytes were written before an error.
    ShortWrite { written: usize },
}

/// Write the entire buffer using libbb's EINTR-aware write loop.
pub fn full_write(fd: RawFd, buffer: &[u8]) -> Result<(), WriteError> {
    // SAFETY: `buffer` is valid for `buffer.len()` bytes for the duration of
    // the call. The caller supplies the destination descriptor.
    let written =
        unsafe { raw::bb_rust_full_write(fd, buffer.as_ptr().cast::<c_void>(), buffer.len()) };
    if written < 0 {
        Err(WriteError::Failed)
    } else if written as usize != buffer.len() {
        Err(WriteError::ShortWrite {
            written: written as usize,
        })
    } else {
        Ok(())
    }
}

/// A NUL-terminated string allocated by libbb.
///
/// The allocation is returned to the C allocator on drop. Keeping this as a
/// dedicated type prevents Rust containers from taking ownership of memory
/// allocated by C.
#[derive(Debug)]
pub struct LibbbString(NonNull<c_char>);

impl LibbbString {
    fn from_raw(pointer: *mut c_char) -> Option<Self> {
        NonNull::new(pointer).map(Self)
    }

    pub fn as_c_str(&self) -> &CStr {
        // SAFETY: Bridge functions return owned, NUL-terminated C strings and
        // the allocation remains alive for the lifetime of `self`.
        unsafe { CStr::from_ptr(self.0.as_ptr()) }
    }

    pub fn as_bytes(&self) -> &[u8] {
        self.as_c_str().to_bytes()
    }
}

impl Drop for LibbbString {
    fn drop(&mut self) {
        // SAFETY: This pointer came from a bridge allocation and is freed once.
        unsafe { raw::bb_rust_free(self.0.as_ptr().cast::<c_void>()) }
    }
}

/// Return libbb's allocated physical current working directory.
///
/// libbb prints a diagnostic and returns `None` on failure.
pub fn current_dir() -> Option<LibbbString> {
    // SAFETY: The bridge takes no arguments and transfers any returned
    // allocation to the caller.
    LibbbString::from_raw(unsafe { raw::bb_rust_getcwd_or_warn() })
}

/// Join a path and filename with BusyBox path semantics.
///
/// A `None` path has the same meaning as an empty path in libbb. Allocation
/// failure follows libbb xfunc behavior and terminates the applet.
pub fn concat_path_file(path: Option<&CStr>, filename: &CStr) -> LibbbString {
    let path_pointer = path.map_or(core::ptr::null(), CStr::as_ptr);
    // SAFETY: Both non-null pointers are NUL-terminated and live for the call.
    // `concat_path_file` is an xfunc and does not return null.
    let result = unsafe { raw::bb_rust_concat_path_file(path_pointer, filename.as_ptr()) };
    LibbbString::from_raw(result).expect("libbb concat_path_file returned null")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CString;
    use std::sync::atomic::{AtomicBool, AtomicI32, AtomicUsize, Ordering};
    use std::sync::{Mutex, MutexGuard};

    static TEST_LOCK: Mutex<()> = Mutex::new(());
    static CLOSED_FD: AtomicI32 = AtomicI32::new(-1);
    static FREE_COUNT: AtomicUsize = AtomicUsize::new(0);
    static GETCWD_FAIL: AtomicBool = AtomicBool::new(false);
    static COPY_FAIL: AtomicBool = AtomicBool::new(false);
    static LAST_MESSAGE: Mutex<Vec<u8>> = Mutex::new(Vec::new());

    fn lock() -> MutexGuard<'static, ()> {
        TEST_LOCK.lock().expect("test lock poisoned")
    }

    unsafe fn copy_message(message: *const c_char) {
        // SAFETY: The wrapper contract supplies a valid C string.
        let bytes = unsafe { CStr::from_ptr(message) }.to_bytes().to_vec();
        *LAST_MESSAGE.lock().expect("message lock poisoned") = bytes;
    }

    #[export_name = "bb_rust_error_msg"]
    unsafe extern "C" fn mock_error_msg(message: *const c_char) {
        // SAFETY: Forwarding the mock ABI contract.
        unsafe { copy_message(message) };
    }

    #[export_name = "bb_rust_perror_msg"]
    unsafe extern "C" fn mock_perror_msg(message: *const c_char) {
        // SAFETY: Forwarding the mock ABI contract.
        unsafe { copy_message(message) };
    }

    #[export_name = "bb_rust_open_input"]
    unsafe extern "C" fn mock_open_input(path: *const c_char) -> c_int {
        // SAFETY: The wrapper contract supplies a valid C string.
        match unsafe { CStr::from_ptr(path) }.to_bytes() {
            b"-" => 0,
            b"missing" => -1,
            _ => 42,
        }
    }

    #[export_name = "bb_rust_copy_to_stdout"]
    extern "C" fn mock_copy_to_stdout(_fd: c_int) -> c_int {
        if COPY_FAIL.load(Ordering::SeqCst) {
            -1
        } else {
            0
        }
    }

    #[export_name = "bb_rust_full_write"]
    unsafe extern "C" fn mock_full_write(
        fd: c_int,
        _buffer: *const c_void,
        length: usize,
    ) -> isize {
        match fd {
            -1 => -1,
            -2 => length.saturating_sub(1) as isize,
            _ => length as isize,
        }
    }

    #[export_name = "bb_rust_close"]
    unsafe extern "C" fn mock_close(fd: c_int) -> c_int {
        CLOSED_FD.store(fd, Ordering::SeqCst);
        0
    }

    #[export_name = "bb_rust_getcwd_or_warn"]
    unsafe extern "C" fn mock_getcwd() -> *mut c_char {
        if GETCWD_FAIL.load(Ordering::SeqCst) {
            return core::ptr::null_mut();
        }
        CString::new("/work")
            .expect("literal has no NUL")
            .into_raw()
    }

    #[export_name = "bb_rust_concat_path_file"]
    unsafe extern "C" fn mock_concat_path_file(
        path: *const c_char,
        filename: *const c_char,
    ) -> *mut c_char {
        let path = if path.is_null() {
            Vec::new()
        } else {
            // SAFETY: The wrapper contract supplies a valid C string.
            unsafe { CStr::from_ptr(path) }.to_bytes().to_vec()
        };
        // SAFETY: The wrapper contract supplies a valid C string.
        let filename = unsafe { CStr::from_ptr(filename) }.to_bytes();
        let mut joined = path;
        if !joined.ends_with(b"/") {
            joined.push(b'/');
        }
        joined.extend_from_slice(filename.strip_prefix(b"/").unwrap_or(filename));
        CString::new(joined).expect("inputs have no NUL").into_raw()
    }

    #[export_name = "bb_rust_free"]
    unsafe extern "C" fn mock_free(pointer: *mut c_void) {
        FREE_COUNT.fetch_add(1, Ordering::SeqCst);
        // SAFETY: Test bridge strings were allocated with CString::into_raw.
        drop(unsafe { CString::from_raw(pointer.cast::<c_char>()) });
    }

    #[test]
    fn messages_use_fixed_c_string_interface() {
        let _guard = lock();
        error_msg(c"plain error");
        assert_eq!(&*LAST_MESSAGE.lock().unwrap(), b"plain error");
        perror_msg(c"open failed");
        assert_eq!(&*LAST_MESSAGE.lock().unwrap(), b"open failed");
    }

    #[test]
    fn input_fd_closes_named_files_but_not_stdin() {
        let _guard = lock();
        CLOSED_FD.store(-1, Ordering::SeqCst);
        drop(open_input(c"file").unwrap());
        assert_eq!(CLOSED_FD.load(Ordering::SeqCst), 42);

        CLOSED_FD.store(-1, Ordering::SeqCst);
        drop(open_input(c"-").unwrap());
        assert_eq!(CLOSED_FD.load(Ordering::SeqCst), -1);
        assert!(matches!(open_input(c"missing"), Err(OpenInputError)));
    }

    #[test]
    fn input_fd_reports_copy_failures() {
        let _guard = lock();
        let input = open_input(c"-").unwrap();
        COPY_FAIL.store(false, Ordering::SeqCst);
        assert_eq!(input.copy_to_stdout(), Ok(()));
        COPY_FAIL.store(true, Ordering::SeqCst);
        assert_eq!(input.copy_to_stdout(), Err(CopyError));
        COPY_FAIL.store(false, Ordering::SeqCst);
    }

    #[test]
    fn full_write_distinguishes_failed_and_partial_writes() {
        let _guard = lock();
        assert_eq!(full_write(1, b"abc"), Ok(()));
        assert_eq!(full_write(-1, b"abc"), Err(WriteError::Failed));
        assert_eq!(
            full_write(-2, b"abc"),
            Err(WriteError::ShortWrite { written: 2 })
        );
    }

    #[test]
    fn libbb_strings_are_readable_and_freed_by_c() {
        let _guard = lock();
        FREE_COUNT.store(0, Ordering::SeqCst);
        GETCWD_FAIL.store(false, Ordering::SeqCst);
        {
            let cwd = current_dir().unwrap();
            assert_eq!(cwd.as_bytes(), b"/work");
            let joined = concat_path_file(Some(c"/tmp"), c"file");
            assert_eq!(joined.as_bytes(), b"/tmp/file");
        }
        assert_eq!(FREE_COUNT.load(Ordering::SeqCst), 2);

        GETCWD_FAIL.store(true, Ordering::SeqCst);
        assert!(current_dir().is_none());
        assert_eq!(FREE_COUNT.load(Ordering::SeqCst), 2);
        GETCWD_FAIL.store(false, Ordering::SeqCst);
    }
}
