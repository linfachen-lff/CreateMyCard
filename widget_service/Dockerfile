# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/widget_service/cloud

WORKDIR /app/widget_service

COPY widget_service/requirements-runtime.txt ./requirements-runtime.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check \
      --index-url https://mirrors.aliyun.com/pypi/simple \
      --trusted-host mirrors.aliyun.com \
      --timeout 120 --retries 5 \
      -r requirements-runtime.txt

COPY widget_service/cloud ./cloud
COPY widget_service/docs ./docs
COPY docs /app/docs

RUN groupadd --gid 10001 widget-service \
    && useradd --uid 10001 --gid widget-service --no-create-home widget-service \
    && mkdir -p /app/widget_service/cloud/workspace /opt/test/logs/genui-agent-service/debug \
    && chown -R widget-service:widget-service \
        /app/widget_service/cloud/workspace /opt/test/logs/genui-agent-service/debug

USER widget-service

EXPOSE 8855
VOLUME ["/app/widget_service/cloud/workspace"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8855/health', timeout=3)"

CMD ["python", "cloud/start_websocket_server.py"]
