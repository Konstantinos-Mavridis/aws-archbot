# ArchBot Backend — Lambda Docker image
# Supports both Lambda (via Mangum) and standalone Fargate (uvicorn)

FROM public.ecr.aws/lambda/python:3.12

WORKDIR /var/task

# Install dependencies
COPY backend/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir ".[]"

# Copy application code
COPY backend/app ./app

# Lambda handler entrypoint
CMD ["app.main.handler"]
