# Testsuite architecture

BusyBox functional tests use one `command.tests` file per applet. Each file
sources `testsuite/testing.sh` and uses either `testing()` for output-based
checks or `testing_script()` for isolated multi-command shell assertions.
Local builds and build-related tests must run through `Dockerfile.build`.

## Legacy-format migration

Issue #53 migrated all 164 remaining `testsuite/applet/testcase` files into
41 applet `.tests` files. The inventory at migration time was:

| applets | migrated cases |
| --- | ---: |
| basename, bunzip2, bzcat, cat, cmp | 8 |
| cp, cut, date, dd | 35 |
| dirname, du, echo, expr, false | 28 |
| find, gunzip, gzip, hostid, hostname, id | 15 |
| ln, ls, md5sum, mkdir, mv | 27 |
| paste, pwd, rm, rmdir, strings | 9 |
| tail, tar, tee, touch, tr | 28 |
| true, uptime, wc, wget, which, xargs | 14 |
| **total** | **164** |

The old directory runner was removed. `testing_script()` preserves its useful
semantics: every case receives a clean directory, shell failure determines the
result, verbose mode exposes captured diagnostics, and feature-dependent cases
use `optional`. Run the normal suite with:

```sh
BUSYBOX_BUILD_IMAGE=busybox-build scripts/docker-testsuite.sh
```

## Privileged isolation

Issue #54 uses Docker because its default PID and mount namespaces separate
the tests from the host. The runner grants only the capability required by
each scenario, drops all others, enables `no-new-privileges`, uses a read-only
root filesystem for runtime checks, and exchanges artifacts through a
short-lived Docker volume. A trap forcibly removes both the init container and
the volume on success, failure, or interruption.

The mount scenario creates a tmpfs with the BusyBox `mount` applet, verifies
I/O, and unmounts it inside the container mount namespace. The init scenario
executes BusyBox `init` as PID 1 and verifies that an inittab `sysinit` child
observes PID 1 as its parent. It then forcibly removes the isolated container.
Neither scenario mounts a writable host directory.

Run both scenarios with:

```sh
BUSYBOX_BUILD_IMAGE=busybox-build scripts/docker-privileged-tests.sh
```

If Docker, its daemon, or isolated `CAP_SYS_ADMIN` mounts are unavailable, the
runner prints an explicit `SKIPPED:` reason and exits successfully. A supported
runtime which starts the scenarios but fails an assertion exits nonzero.

## libbb unit tests

Issue #55 uses the existing `CONFIG_UNIT_TEST` applet rather than introducing
a second C test ABI. The containerized focused entry point is:

```sh
BUSYBOX_BUILD_IMAGE=busybox-build scripts/docker-libbb-unit-tests.sh
```

See `docs/unit-tests.txt` for authoring rules and the covered function groups.
