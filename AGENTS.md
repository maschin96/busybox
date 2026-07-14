# Lokale Builds

- Lokale Builds müssen immer in einem Docker-Container auf Basis von `Dockerfile.build` ausgeführt werden. Build-Tools wie `make`, `cargo`, Compiler oder Linker dürfen nicht direkt auf dem Host für dieses Repository gestartet werden.
- Das Build-Image wird bei Bedarf auf dem Host erstellt:

  ```sh
  docker build -f Dockerfile.build -t busybox-build .
  ```

- Der Quellbaum wird nach `/work/src` eingebunden. Ein vollständiger Standard-Build wird so ausgeführt:

  ```sh
  docker run --rm -v "$PWD:/work/src" -w /work/src busybox-build \
    sh -lc 'make -j"$(nproc)"'
  ```

- Andere Build-Ziele und buildnahe Prüfungen werden nach demselben Muster im Container ausgeführt, zum Beispiel:

  ```sh
  docker run --rm -v "$PWD:/work/src" -w /work/src busybox-build \
    sh -lc 'make test'
  ```

- Falls Abhängigkeiten fehlen, muss `Dockerfile.build` erweitert und das Image neu gebaut werden. Es ist nicht zulässig, den Build deshalb auf den Host zu verlagern.
