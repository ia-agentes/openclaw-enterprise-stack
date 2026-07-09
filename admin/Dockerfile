FROM python:3.12-slim

WORKDIR /app

COPY admin /app/admin
COPY scripts/status.py /app/scripts/status.py
COPY config /app/config

ENV OCES_ADMIN_PORT=8080

EXPOSE 8080

CMD ["python", "/app/admin/server.py"]
