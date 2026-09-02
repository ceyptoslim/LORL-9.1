FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     gcc libpq-dev

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Ensure /app is writable by the non-root user (SQLite needs write access)
RUN useradd -m lorl && chown -R lorl:lorl /app
USER lorl

# Default to SQLite in /tmp (writable by all users)
ENV LORL_DB_URL=sqlite:////tmp/lorl.db

EXPOSE 8000

CMD ["uvicorn", "lorl.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
