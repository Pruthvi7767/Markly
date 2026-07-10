FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies (will cache this layer unless pyproject.toml changes)
RUN pip install --no-cache-dir -e .

# Copy project source
COPY . .

# Install the application
RUN pip install --no-cache-dir -e .

# Define entrypoint
ENTRYPOINT ["markly"]
