FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser

COPY requirements-runtime.txt ./
RUN python -m pip install \
    --require-hashes \
    --only-binary=:all: \
    --index-url https://pypi.org/simple \
    --requirement requirements-runtime.txt

COPY app.py ./
COPY src/ ./src/
COPY assets/ ./assets/
COPY config/ ./config/
COPY data/published/ ./data/published/
COPY .streamlit/ ./.streamlit/

RUN mkdir -p /app/data/processed \
    && chown -R appuser:appuser /app

USER 10001:10001

EXPOSE 8080

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8080", "--server.headless=true", "--browser.gatherUsageStats=false"]
