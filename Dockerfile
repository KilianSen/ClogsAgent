FROM python:3.14-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import time, sys; sys.exit(0 if time.time() - float(open('/tmp/healthy').read()) < 90 else 1)"

ENV FLASK_ENV=production
ENV CLOGS_BACKEND_URL=http://backend.docker.host:8000

CMD ["python", "main.py"]