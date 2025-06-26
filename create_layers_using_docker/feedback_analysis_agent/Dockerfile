# Use the official AWS Lambda Python 3.11 runtime as base image
FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies that might be needed for textblob/nltk
RUN yum update -y && \
    yum install -y gcc gcc-c++ make && \
    yum clean all

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install Python dependencies to /opt/python/ (Lambda layer structure)
RUN pip install --upgrade pip && \
    pip install -r requirements.txt -t /opt/python/

# Download NLTK data that textblob might need
RUN python -c "import nltk; nltk.download('punkt', download_dir='/opt/python/nltk_data'); nltk.download('brown', download_dir='/opt/python/nltk_data')" || true

# Set the working directory
WORKDIR /opt

# Default command
CMD ["echo", "OpenAI Agents Lambda layer built successfully"]