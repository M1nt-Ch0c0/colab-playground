FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QP_ROOT=/data \
    QP_HOST=0.0.0.0 \
    QP_PORT=8787

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY draw_studio ./draw_studio
COPY --from=web /build/dist ./web/dist

RUN useradd -m -u 1000 studio \
    && mkdir -p /data/out \
    && chown -R studio:studio /app /data

USER studio

VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=3)" || exit 1

CMD ["python3", "/app/app.py"]
