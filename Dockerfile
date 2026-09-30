FROM python:3.13-alpine

WORKDIR /app
COPY app/ /app/app/
RUN addgroup -S app && adduser -S app -G app && mkdir -p /data && chown app:app /data
USER app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080 DB_PATH=/data/lab07.sqlite3
EXPOSE 8080
CMD ["python", "-m", "app.server"]

