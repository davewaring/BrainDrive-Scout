FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY static/ static/

# Create logs directory
RUN mkdir -p logs

# Install the package
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "scout.main:app", "--host", "0.0.0.0", "--port", "8000"]
