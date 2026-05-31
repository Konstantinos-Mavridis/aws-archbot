# ArchBot Backend — Lambda Docker image
# Build context is the `backend/` directory (set by CDK DockerImageCode.from_image_asset).
# Supports both Lambda (via Mangum) and standalone Fargate (uvicorn).

FROM public.ecr.aws/lambda/python:3.12

WORKDIR /var/task

# Install dependencies first for better layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[]"

# Copy application source
COPY app ./app

# Lambda handler entrypoint
CMD ["app.main.handler"]
