FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
# Use the image's Python 3.11 here (pyproject prefers uv-managed Python for local dev).
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    AVATAR_CATALOG=/app/shared/avatar/catalog.json

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

# The avatar parts library lives in the repo's shared/ folder, outside this build context.
# docker-compose.yml passes it in as the named context "shared"; with plain docker build, add
# --build-context shared=../shared.
COPY --from=shared avatar/catalog.json ./shared/avatar/catalog.json
COPY app ./app

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
