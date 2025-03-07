# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install Poetry and build dependencies
RUN pip install poetry==2.1.1
RUN pip install poetry-plugin-export
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy only requirements files first
COPY pyproject.toml poetry.lock* ./

# Configure Poetry
RUN poetry config virtualenvs.create false
RUN poetry export -f requirements.txt --without dev > requirements.txt

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Copy requirements from builder
COPY --from=builder /app/requirements.txt .

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y build-essential && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy application code
COPY . .


# Set environment variables
ENV PORT=8080
ENV HOST="0.0.0.0"

# Run the application
# Using shell form to properly expand environment variables
CMD sh -c "PYTHONPATH=/app/server/src python server/src/server/app.py"
