#!/bin/sh
set -eu

image="${BUSYBOX_BUILD_IMAGE:-busybox-build:rust-1.79}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
volume="busybox-privileged-tests-$$"
cid=

cleanup()
{
	if test -n "$cid"; then
		docker rm -f "$cid" >/dev/null 2>&1 || true
	fi
	docker volume rm -f "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

if ! command -v docker >/dev/null 2>&1; then
	echo "SKIPPED: privileged tests (Docker is unavailable)"
	exit 0
fi

if ! docker info >/dev/null 2>&1; then
	echo "SKIPPED: privileged tests (Docker daemon is unavailable)"
	exit 0
fi

if ! docker image inspect "$image" >/dev/null 2>&1; then
	docker buildx build --load -f "$root/Dockerfile.build" -t "$image" "$root"
fi

if ! docker run --rm --cap-drop ALL --cap-add SYS_ADMIN \
	--tmpfs /tmp:rw,nosuid,nodev "$image" sh -eu -c '
		mkdir /tmp/mount-probe
		mount -t tmpfs tmpfs /tmp/mount-probe
		umount /tmp/mount-probe
	' >/dev/null 2>&1
then
	echo "SKIPPED: privileged tests (isolated CAP_SYS_ADMIN mounts are unavailable)"
	exit 0
fi

docker volume create "$volume" >/dev/null
docker run --rm \
	-v "$root:/src:ro" \
	-v "$volume:/artifacts" \
	"$image" \
	sh -eu -c '
		rsync -a --delete \
			--exclude .git \
			--exclude build \
			--exclude ".config*" \
			--exclude ".kernelrelease*" \
			--exclude "rust/target" \
			--exclude "__pycache__" \
			/src/ /work/src/
		make allnoconfig >/dev/null
		python3 scripts/ci_set_config.py \
			BUSYBOX=y CAT=y MOUNT=y UMOUNT=y INIT=y FEATURE_USE_INITTAB=y \
			ASH=y SH_IS_ASH=y
		yes "" | make oldconfig >/dev/null
		make -j"$(nproc)" busybox >/dev/null
		cp busybox /artifacts/busybox
		cp testsuite/privileged-init.inittab /artifacts/inittab
	'

docker run --rm --read-only \
	--security-opt no-new-privileges \
	--cap-drop ALL --cap-add SYS_ADMIN \
	--tmpfs /tmp:rw,nosuid,nodev \
	-v "$volume:/artifacts:ro" \
	"$image" sh -eu -c '
		mkdir /tmp/mnt
		/artifacts/busybox mount -t tmpfs -o size=64k tmpfs /tmp/mnt
		trap "/artifacts/busybox umount /tmp/mnt" EXIT
		printf isolated > /tmp/mnt/probe
		test "$(/artifacts/busybox cat /tmp/mnt/probe)" = isolated
		/artifacts/busybox umount /tmp/mnt
		trap - EXIT
		echo "PASS: mount in an isolated Docker mount namespace"
	'

cid=$(docker run -d --read-only \
	--security-opt no-new-privileges \
	--cap-drop ALL --cap-add SYS_BOOT \
	--tmpfs /tmp:rw,nosuid,nodev,exec \
	--tmpfs /etc:rw,nosuid,nodev \
	--tmpfs /run:rw,nosuid,nodev \
	-v "$volume:/artifacts" \
	"$image" sh -eu -c '
		cp /artifacts/busybox /tmp/busybox
		cp /artifacts/inittab /etc/inittab
		exec /tmp/busybox init
	')

passed=
attempt=0
while test "$attempt" -lt 20; do
	if docker run --rm -v "$volume:/artifacts:ro" "$image" \
		test -f /artifacts/init-result
	then
		passed=1
		break
	fi
	attempt=$((attempt + 1))
	sleep 1
done

docker rm -f "$cid" >/dev/null
cid=

if test -z "$passed"; then
	echo "FAIL: BusyBox init did not execute sysinit as PID 1" >&2
	exit 1
fi
echo "PASS: init executed sysinit as PID 1 in an isolated Docker PID namespace"
