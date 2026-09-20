FROM rust:1.89-bookworm AS cedar-builder

WORKDIR /src
COPY services/cedar_pdp/Cargo.toml services/cedar_pdp/Cargo.lock services/cedar_pdp/
COPY services/cedar_pdp/src services/cedar_pdp/src
RUN cargo build --locked --release --manifest-path services/cedar_pdp/Cargo.toml

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN groupadd --system manifest && useradd --system --gid manifest --home-dir /app manifest
WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps apps
COPY packages packages
COPY fixtures fixtures
COPY policies policies
COPY scripts/check_cedar_ready.py scripts/start_checkpoint_12_cloud.sh scripts/
COPY --from=cedar-builder /src/services/cedar_pdp/target/release/manifest-cedar-pdp /app/bin/manifest-cedar-pdp

RUN python -m pip install --no-cache-dir '.[bedrock_mantle]' && \
    chmod 0555 /app/bin/manifest-cedar-pdp /app/scripts/start_checkpoint_12_cloud.sh && \
    chown -R manifest:manifest /app

USER manifest
EXPOSE 8080

ENTRYPOINT ["/app/scripts/start_checkpoint_12_cloud.sh"]
