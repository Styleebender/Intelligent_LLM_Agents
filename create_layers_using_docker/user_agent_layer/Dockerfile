# Use the official AWS Lambda Python 3.11 runtime as base image
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install Python dependencies to /opt/python/ (Lambda layer structure)
RUN pip install -r requirements.txt -t /opt/python/

# Set the working directory
WORKDIR /opt

# Default command
CMD ["echo", "Lambda layer built successfully"]