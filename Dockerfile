FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ACCOUNTING_DB_PATH=/tmp/fastrack/accounting.db

WORKDIR /app/PythonApplication1

COPY PythonApplication1/requirements.txt /app/PythonApplication1/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY PythonApplication1 /app/PythonApplication1

EXPOSE 8080

CMD ["/bin/sh", "-c", "mkdir -p /tmp/fastrack && if [ ! -f \"$ACCOUNTING_DB_PATH\" ] && [ -f /app/PythonApplication1/data/accounting.db ]; then cp /app/PythonApplication1/data/accounting.db \"$ACCOUNTING_DB_PATH\"; fi && exec gunicorn --bind :8080 --workers 2 --threads 8 --timeout 120 'web_app:create_app()'"]
