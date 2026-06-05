FROM node:20-slim

# Install minimal dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install VS Code extensions (optional; mostly installed via extension marketplace)
# Placeholder for any future npm-based tooling
WORKDIR /code
CMD ["bash"]