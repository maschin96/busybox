use core::ffi::{c_char, c_int};

use crate::ffi::run_applet;

#[no_mangle]
pub extern "C" fn rust_true_main(
    argc: c_int,
    argv: *mut *mut c_char,
) -> c_int {
    run_applet(argc, argv, |_| 0)
}
