FROM python:3.12-slim

# Set working directory
WORKDIR /app/server

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Run with hot reload for development
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]