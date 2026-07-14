/* vi: set sw=4 ts=4: */
/*
 * Small, stable C ABI for Rust applets.
 *
 * Licensed under GPLv2, see file LICENSE in this source tree.
 */
//kbuild:lib-$(CONFIG_FEATURE_RUST_APPLETS) += rust_ffi.o

#include "libbb.h"
#include "rust_ffi.h"

void bb_rust_error_msg(const char *message)
{
	bb_error_msg("%s", message);
}

void bb_rust_perror_msg(const char *message)
{
	bb_perror_msg("%s", message);
}

int bb_rust_open_input(const char *path)
{
	return open_or_warn_stdin(path);
}

int bb_rust_copy_to_stdout(int fd)
{
	return bb_copyfd_eof(fd, STDOUT_FILENO) < 0 ? -1 : 0;
}

ssize_t bb_rust_full_write(int fd, const void *buffer, size_t length)
{
	return full_write(fd, buffer, length);
}

int bb_rust_close(int fd)
{
	return close(fd);
}

char *bb_rust_getcwd_or_warn(void)
{
	return xrealloc_getcwd_or_warn(NULL);
}

char *bb_rust_concat_path_file(const char *path, const char *filename)
{
	return concat_path_file(path, filename);
}

void bb_rust_free(void *pointer)
{
	free(pointer);
}
