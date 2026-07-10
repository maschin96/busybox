use core::ffi::{c_char, c_int};

use crate::ffi::run_applet;

#[no_mangle]
pub unsafe extern "C" fn rust_true_main(argc: c_int, argv: *mut *mut c_char) -> c_int {
    // SAFETY: BusyBox calls applet entry points with its normal argc/argv ABI.
    unsafe { run_applet(argc, argv, |_| 0) }
}

#[no_mangle]
pub unsafe extern "C" fn rust_false_main(argc: c_int, argv: *mut *mut c_char) -> c_int {
    // SAFETY: BusyBox calls applet entry points with its normal argc/argv ABI.
    unsafe { run_applet(argc, argv, |_| 1) }
}
