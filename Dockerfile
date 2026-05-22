FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ACCOUNTING_DB_PATH=/tmp/fastrack/accounting.db

WORKDIR /app/PythonApplication1

COPY PythonApplication1/requirements.txt /app/PythonApplication1/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY PythonApplication1 /app/PythonApplication1
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD exec gunicorn --bind :${PORT:-8080} --workers 2 --threads 8 --timeout 120 "web_app:create_app()"
