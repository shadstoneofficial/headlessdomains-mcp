FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# Legacy MCP v1 runtime; the ChatGPT extension has a separate MCP v2 environment.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Read-only, localhost-only protocol check; never invokes business tools.
RUN python scripts/smoke_legacy.py

EXPOSE 8080

# Run the server script directly
# The PORT environment variable (set by Railway) triggers HTTP/SSE mode in main()
CMD ["python", "server.py"]
