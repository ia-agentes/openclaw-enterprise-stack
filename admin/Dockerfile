FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir PyYAML Jinja2

COPY admin /app/admin
COPY scripts/status.py /app/scripts/status.py
COPY scripts/generate.py /app/scripts/generate.py
COPY templates /app/templates
COPY config /app/config

ENV OCES_ADMIN_PORT=8080

EXPOSE 8080

CMD ["python", "/app/admin/server.py"]
