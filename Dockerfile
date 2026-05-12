##
## downgrade_exec builder:
##  Cross-compiles the downgrade_exec binary natively on $BUILDPLATFORM, regardless
##  of the target arch — Go's cross-compiler emits the right ELF without
##  ever running foreign-arch code under QEMU.
##
FROM --platform=$BUILDPLATFORM golang:1.25-alpine3.21 AS downgrade_exec-builder
ARG TARGETOS
ARG TARGETARCH
# llvm provides llvm-strip, which (unlike binutils strip) handles any target arch
RUN apk add --no-cache llvm
WORKDIR /src
COPY downgrade_exec/ ./
RUN go test ./...
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -trimpath -buildvcs=false -ldflags="-s -w -buildid=" -o /downgrade_exec . && \
    llvm-strip --strip-all /downgrade_exec && \
    # setuid nobody: the binary must be owned by nobody and have the setuid bit so that
    # any process (running as any uid) that execs it will run with euid=nobody, allowing
    # downgrade_exec to irreversibly drop privileges via setresuid before execing the
    # target command.
    chown 65534:65534 /downgrade_exec && \
    chmod u+s /downgrade_exec

FROM scratch
COPY --link --from=downgrade_exec-builder /downgrade_exec /opt/ai-contained-provider-shell/bin/downgrade_exec
COPY . /opt/ai-contained-provider-shell
