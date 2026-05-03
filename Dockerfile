FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# Install standard dependencies, plus FastAPI and Uvicorn for HTTP serving
RUN pip install "mcp[cli]" requests fastapi uvicorn

COPY . .

EXPOSE 8080

# Run the server script directly
# The PORT environment variable (set by Railway) triggers HTTP/SSE mode in main()
CMD ["python", "server.py"]
