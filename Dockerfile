FROM python:3.15-slim-bookworm@sha256:575f8bc12ec26542e0678bc6b60e385218248019d433157ec327264a78c3a853

LABEL org.opencontainers.image.title="Tender Meridian" \
    org.opencontainers.image.description="Explainable EU tender intelligence dashboard" \
    org.opencontainers.image.source="https://github.com/civanft/ai-tender-intelligence"

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

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8080/_stcore/health', timeout=4); raise SystemExit(0 if response.status == 200 else 1)"]

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8080", "--server.headless=true", "--browser.gatherUsageStats=false"]
