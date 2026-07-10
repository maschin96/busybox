#!/bin/sh
set -eu

image="${BUSYBOX_BUILD_IMAGE:-busybox-build:local}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if ! docker image inspect "$image" >/dev/null 2>&1; then
	docker buildx build --load -f "$root/Dockerfile.build" -t "$image" "$root"
fi

if [ "$#" -eq 0 ]; then
	set -- defconfig all
fi

docker run --rm \
	-v "$root:/src:ro" \
	"$image" \
	sh -eu -c '
		rsync -a --delete \
			--exclude .git \
			--exclude ".kernelrelease*" \
			/src/ /work/src/
		for target do
			if [ "$target" = all ]; then
				make -j"$(nproc)"
			else
				make "$target"
			fi
		done
	' sh "$@"
