# Use a minimal, secure Python base image
FROM python:3.11-slim

# Set environment variables for security and performance
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install only the necessary system packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        iputils-ping \
        traceroute \
        dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Set a non-root user for security
RUN useradd -m appuser
WORKDIR /app
USER appuser

# Copy only requirements first for better build caching
COPY --chown=appuser:appuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY --chown=appuser:appuser . .

# Use .env file for configuration (mount at runtime)
# CMD will be run as appuser
CMD ["python", "network_monitor.py"]

# Link image to github repository
LABEL org.opencontainers.image.source https://github.com/Paul1404/SpectraIIM