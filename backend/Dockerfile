FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (cache-friendly)
COPY requirements.txt /app/requirements.txt

# Upgrade pip (required for MediaPipe)
RUN pip install --upgrade pip

# Install MediaPipe FIRST (forces correct version)
RUN pip install --no-cache-dir mediapipe==0.10.20

# Install the rest of your dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy your application code
COPY . .

RUN mkdir -p /app/uploads /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
