use core::ffi::{c_char, c_int};
use std::env;
use std::ffi::CStr;
use std::io::{self, Write};
use std::os::unix::ffi::OsStrExt;

use crate::ffi::run_applet;
use crate::ffi::RawArgv;

const EXIT_SUCCESS: c_int = 0;
const EXIT_FAILURE: c_int = 1;

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

#[no_mangle]
pub unsafe extern "C" fn rust_basename_main(argc: c_int, argv: *mut *mut c_char) -> c_int {
    // SAFETY: BusyBox calls applet entry points with its normal argc/argv ABI.
    unsafe { run_applet(argc, argv, basename_main) }
}

#[no_mangle]
pub unsafe extern "C" fn rust_dirname_main(argc: c_int, argv: *mut *mut c_char) -> c_int {
    // SAFETY: BusyBox calls applet entry points with its normal argc/argv ABI.
    unsafe { run_applet(argc, argv, dirname_main) }
}

#[no_mangle]
pub unsafe extern "C" fn rust_pwd_main(argc: c_int, argv: *mut *mut c_char) -> c_int {
    // SAFETY: BusyBox calls applet entry points with its normal argc/argv ABI.
    unsafe { run_applet(argc, argv, pwd_main) }
}

fn argv_bytes(argv: RawArgv) -> Option<Vec<Vec<u8>>> {
    let mut args = Vec::with_capacity(argv.argc() as usize);
    for index in 0..argv.argc() {
        // SAFETY: RawArgv was constructed from BusyBox's argc/argv pair. Each
        // argument pointer is expected to be a valid NUL-terminated C string.
        let ptr = unsafe { *argv.as_ptr().add(index as usize) };
        if ptr.is_null() {
            return None;
        }
        // SAFETY: See the pointer validity note above.
        args.push(unsafe { CStr::from_ptr(ptr) }.to_bytes().to_vec());
    }
    Some(args)
}

fn write_line(bytes: &[u8]) -> c_int {
    let mut stdout = io::stdout().lock();
    if stdout.write_all(bytes).is_err() || stdout.write_all(b"\n").is_err() {
        return EXIT_FAILURE;
    }
    EXIT_SUCCESS
}

fn write_lines(lines: &[Vec<u8>]) -> c_int {
    for line in lines {
        if write_line(line) != EXIT_SUCCESS {
            return EXIT_FAILURE;
        }
    }
    EXIT_SUCCESS
}

fn usage_error() -> c_int {
    EXIT_FAILURE
}

fn basename_main(argv: RawArgv) -> c_int {
    let Some(args) = argv_bytes(argv) else {
        return usage_error();
    };
    let mut suffix: Option<Vec<u8>> = None;
    let mut all_args_are_files = false;
    let mut files: Vec<Vec<u8>> = Vec::new();
    let mut index = 1;

    while index < args.len() {
        match args[index].as_slice() {
            b"-a" => {
                all_args_are_files = true;
                index += 1;
            }
            b"-s" => {
                if index + 1 >= args.len() {
                    return usage_error();
                }
                suffix = Some(args[index + 1].clone());
                all_args_are_files = true;
                index += 2;
            }
            b"--" => {
                index += 1;
                break;
            }
            _ => break,
        }
    }

    files.extend(args[index..].iter().cloned());
    if files.is_empty() {
        return usage_error();
    }
    if !all_args_are_files && files.len() > 2 {
        return usage_error();
    }
    if !all_args_are_files && files.len() == 2 {
        suffix = Some(files.pop().expect("suffix exists"));
    }

    let output: Vec<Vec<u8>> = files
        .iter()
        .map(|file| strip_basename_suffix(last_path_component_strip(file), suffix.as_deref()))
        .collect();
    write_lines(&output)
}

fn last_path_component_strip(path: &[u8]) -> Vec<u8> {
    if path.is_empty() {
        return Vec::new();
    }

    let mut end = path.len();
    while end > 1 && path[end - 1] == b'/' {
        end -= 1;
    }

    let stripped = &path[..end];
    if stripped == b"/" {
        return b"/".to_vec();
    }
    match stripped.iter().rposition(|byte| *byte == b'/') {
        Some(index) => stripped[index + 1..].to_vec(),
        None => stripped.to_vec(),
    }
}

fn strip_basename_suffix(mut base: Vec<u8>, suffix: Option<&[u8]>) -> Vec<u8> {
    if let Some(suffix) = suffix {
        if base.len() > suffix.len() && base.ends_with(suffix) {
            base.truncate(base.len() - suffix.len());
        }
    }
    base
}

fn dirname_main(argv: RawArgv) -> c_int {
    let Some(args) = argv_bytes(argv) else {
        return usage_error();
    };
    let args = skip_dash_dash(&args);
    if args.len() != 1 {
        return usage_error();
    }
    write_line(&dirname_of(&args[0]))
}

fn skip_dash_dash(args: &[Vec<u8>]) -> &[Vec<u8>] {
    let args = &args[1..];
    if args.first().is_some_and(|arg| arg.as_slice() == b"--") {
        &args[1..]
    } else {
        args
    }
}

fn dirname_of(path: &[u8]) -> Vec<u8> {
    if path.is_empty() {
        return b".".to_vec();
    }

    let mut end = path.len();
    while end > 1 && path[end - 1] == b'/' {
        end -= 1;
    }
    while end > 0 && path[end - 1] != b'/' {
        end -= 1;
    }
    if end == 0 {
        return b".".to_vec();
    }
    while end > 1 && path[end - 1] == b'/' {
        end -= 1;
    }
    path[..end].to_vec()
}

fn pwd_main(_: RawArgv) -> c_int {
    match env::current_dir() {
        Ok(path) => write_line(path.as_os_str().as_bytes()),
        Err(_) => EXIT_FAILURE,
    }
}
