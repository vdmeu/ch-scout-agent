FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run — Railway sets $PORT dynamically; fall back to 8000 for local dev
EXPOSE 8000
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
