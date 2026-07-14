/* vi: set sw=4 ts=4: */
/*
 * Utility routines.
 *
 * Copyright (C) 1999-2004 by Erik Andersen <andersen@codepoet.org>
 *
 * Licensed under GPLv2 or later, see file LICENSE in this source tree.
 */
#include "libbb.h"

/*
 * Write all of the supplied buffer out to a file.
 * This does multiple writes as necessary.
 * Returns the amount written, or -1 if error was seen
 * on the very first write.
 */
ssize_t FAST_FUNC full_write(int fd, const void *buf, size_t len)
{
	ssize_t cc;
	ssize_t total;

	total = 0;

	while (len) {
		cc = safe_write(fd, buf, len);

		if (cc < 0) {
			if (total) {
				/* we already wrote some! */
				/* user can do another write to know the error code */
				return total;
			}
			return cc;  /* write() returns -1 on failure. */
		}

		total += cc;
		buf = ((const char *)buf) + cc;
		len -= cc;
	}

	return total;
}

#if ENABLE_UNIT_TEST

BBUNIT_DEFINE_TEST(full_write_pipe)
{
	int fds[2] = { -1, -1 };
	char buf[4] = { 0, 0, 0, 0 };

	BBUNIT_ASSERT_EQ(0, pipe(fds));
	BBUNIT_ASSERT_EQ(3, full_write(fds[1], "abc", 3));
	close(fds[1]);
	fds[1] = -1;
	BBUNIT_ASSERT_EQ(3, read(fds[0], buf, sizeof(buf)));
	BBUNIT_ASSERT_STREQ("abc", buf);

	BBUNIT_ENDTEST;

	if (fds[0] >= 0)
		close(fds[0]);
	if (fds[1] >= 0)
		close(fds[1]);
}

BBUNIT_DEFINE_TEST(full_write_error)
{
	errno = 0;
	BBUNIT_ASSERT_EQ(-1, full_write(-1, "x", 1));
	BBUNIT_ASSERT_EQ(EBADF, errno);

	BBUNIT_ENDTEST;
}

#endif /* ENABLE_UNIT_TEST */
