FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QP_ROOT=/data \
    QP_HOST=0.0.0.0 \
    QP_PORT=8787

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py jobs.py store.py ui.py colab_backend.py colab_worker.py ./
COPY h3_skills ./h3_skills

RUN useradd -m -u 1000 studio \
    && mkdir -p /data/out \
    && chown -R studio:studio /app /data

USER studio

VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=3)" || exit 1

CMD ["python3", "/app/app.py"]
