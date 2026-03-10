FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages to system Python
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create unprivileged user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

CMD ["python", "bot.py"]
