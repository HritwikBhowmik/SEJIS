# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=6969

# Install system dependencies required for WeasyPrint and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    media-types \
    && rm -rf /var/lib/apt/lists/*

# RUN apt-get update && apt-get install -y \
#     build-essential \
#     python3-dev \
#     libpango-1.0-0 \
#     libharfbuzz-0b \
#     libpangoft2-1.0-0 \
#     libffi-dev \
#     libjpeg-dev \
#     libopenjp2-7-dev \
#     zlib1g-dev \
#     && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./app /app/app
COPY ./frontend /app/frontend
COPY run.py /app/

# Expose port 6969
# EXPOSE 6969

# Start the application
CMD ["python", "run.py"]
