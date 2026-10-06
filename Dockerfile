FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

# Install dependencies first so they cache separately from source changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY src ./src
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH" HOST=0.0.0.0 PORT=8080
EXPOSE 8080
USER nobody

CMD ["news-verifier"]
