FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY main.py .

# Expose port 5500
EXPOSE 5500

# Run the combined bot by default (runs both Telegram and Discord)
CMD ["python", "main.py"]