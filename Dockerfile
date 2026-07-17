# Python base image
FROM python:3.12-slim

# Install Node.js
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Prevent Python from buffering output
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Build Tailwind and collect static files
RUN python manage.py tailwind install && \
    python manage.py tailwind build && \
    python manage.py collectstatic --noinput

# Railway will inject PORT automatically
CMD ["gunicorn", "your_project.wsgi:application", "--bind", "0.0.0.0:8000"]