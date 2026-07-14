/*
 * Stable C ABI exposed to Rust applets.
 *
 * Keep this surface small.  Rust code must not call FAST_FUNC or variadic
 * libbb functions directly; wrappers here use the platform C calling
 * convention and fixed signatures.
 */
#ifndef BB_RUST_FFI_H
#define BB_RUST_FFI_H 1

#include <stddef.h>
#include <sys/types.h>

void bb_rust_error_msg(const char *message);
void bb_rust_perror_msg(const char *message);

int bb_rust_open_input(const char *path);
int bb_rust_copy_to_stdout(int fd);
ssize_t bb_rust_full_write(int fd, const void *buffer, size_t length);
int bb_rust_close(int fd);

char *bb_rust_getcwd_or_warn(void);
char *bb_rust_concat_path_file(const char *path, const char *filename);
void bb_rust_free(void *pointer);

#endif
