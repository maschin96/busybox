#!/bin/sh
set -eu

image="${BUSYBOX_BUILD_IMAGE:-busybox-build:rust-1.79}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if ! docker image inspect "$image" >/dev/null 2>&1; then
	docker buildx build --load -f "$root/Dockerfile.build" -t "$image" "$root"
fi

docker run --rm \
	-v "$root:/src:ro" \
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
		# TEST pulls the skip_whitespace object from libbb.a so its test-only
		# registrations are present in the focused unit-test binary.
		python3 scripts/ci_set_config.py BUSYBOX=y UNIT_TEST=y TEST=y
		yes "" | make oldconfig >/dev/null
		make -j"$(nproc)" busybox >/dev/null
		./busybox unit
	'
