FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for geospatial libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
