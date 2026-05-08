##
## Stage 1: Nix builder — system binary closure (git)
##
FROM nixos/nix:latest AS nix-builder

RUN echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf && \
    echo 'filter-syscalls = false' >> /etc/nix/nix.conf

WORKDIR /build
COPY flake.nix ./
COPY flake.loc[k] ./
RUN nix build

RUN mkdir -p /export/nix/store && \
    cp -va $(nix-store -qR result/) /export/nix/store/

##
## Final: FROM scratch — nix closure + Python source
##
FROM scratch

COPY --link --from=nix-builder /export/ /
COPY src/ /opt/ai-contained-provider-shell/src/
COPY pyproject.toml /opt/ai-contained-provider-shell/pyproject.toml
