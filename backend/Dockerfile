# Backend Dockerfile
FROM python:3.11

ARG TARGETOS
ARG TARGETARCH
ARG TARGETVARIANT

# Install system dependencies
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set the working directory
WORKDIR /backend

# Copy only dependencies
COPY pyproject.toml poetry.lock* ./

# Install all dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy the rest of application code
COPY . .

HEALTHCHECK --interval=300s --timeout=5s --start-period=10s --start-interval=1s --retries=3 CMD [ "curl", "-f", "http://localhost:8000/health" ]

ENTRYPOINT [ "uvicorn", "app.server:app", "--host", "0.0.0.0" ]
