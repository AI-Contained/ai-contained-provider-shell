##
## Stage 1: Nix builder — install git and extract the runtime closure
##
FROM nixos/nix:latest AS nix-builder

RUN echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf && \
    echo 'filter-syscalls = false' >> /etc/nix/nix.conf

WORKDIR /build
COPY flake.nix ./
COPY flake.loc[k] ./
RUN nix build

RUN mkdir /nix-closure && \
    cp -va $(nix-store -qR result/) /nix-closure/

##
## Stage 2: Wheel builder — build the Python provider package
##
FROM python:3.12-alpine AS wheel-builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir build && \
    python -m build --wheel --outdir /wheels/

##
## Final stage: provider image
##
FROM scratch

COPY --link --from=nix-builder /nix-closure/ /nix/store/
COPY --link --from=wheel-builder /wheels/ /opt/ai-contained-provider-shell/wheel/
