/* vi: set sw=4 ts=4: */
/*
 * skip_whitespace implementation for busybox
 *
 * Copyright (C) 2003  Manuel Novoa III  <mjn3@codepoet.org>
 *
 * Licensed under GPLv2 or later, see file LICENSE in this source tree.
 */
#include "libbb.h"

char* FAST_FUNC skip_whitespace(const char *s)
{
	/* In POSIX/C locale (the only locale we care about: do we REALLY want
	 * to allow Unicode whitespace in, say, .conf files? nuts!)
	 * isspace is only these chars: "\t\n\v\f\r" and space.
	 * "\t\n\v\f\r" happen to have ASCII codes 9,10,11,12,13.
	 * Use that.
	 */
	while (*s == ' ' || (unsigned char)(*s - 9) <= (13 - 9))
		s++;

	return (char *) s;
}

char* FAST_FUNC skip_non_whitespace(const char *s)
{
	while (*s != '\0' && *s != ' ' && (unsigned char)(*s - 9) > (13 - 9))
		s++;

	return (char *) s;
}

char* FAST_FUNC skip_dev_pfx(const char *tty_name)
{
	char *unprefixed = is_prefixed_with(tty_name, "/dev/");
	return unprefixed ? unprefixed : (char*)tty_name;
}

#if ENABLE_UNIT_TEST

BBUNIT_DEFINE_TEST(skip_whitespace_boundaries)
{
	BBUNIT_ASSERT_STREQ("word", skip_whitespace(" \t\n\v\f\rword"));
	BBUNIT_ASSERT_STREQ("", skip_whitespace(" \t\n\v\f\r"));
	BBUNIT_ASSERT_STREQ(" word", skip_non_whitespace("word word"));
	BBUNIT_ASSERT_STREQ("", skip_non_whitespace(""));

	BBUNIT_ENDTEST;
}

BBUNIT_DEFINE_TEST(skip_dev_prefix)
{
	BBUNIT_ASSERT_STREQ("tty0", skip_dev_pfx("/dev/tty0"));
	BBUNIT_ASSERT_STREQ("tty0", skip_dev_pfx("tty0"));
	BBUNIT_ASSERT_STREQ("", skip_dev_pfx("/dev/"));

	BBUNIT_ENDTEST;
}

#endif /* ENABLE_UNIT_TEST */
