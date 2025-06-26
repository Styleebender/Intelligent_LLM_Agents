@echo off
echo Building Lambda layer with Docker...

REM Clean up any existing python directory
if exist python rmdir /s /q python

REM Build the Docker image
docker build -t lambda-openai-layer .

REM Create container and copy the layer contents
docker create --name temp-container lambda-openai-layer
docker cp temp-container:/opt/python ./python
docker rm temp-container

REM Create the zip file for Lambda layer
powershell Compress-Archive -Path python -DestinationPath openai-layer.zip -Force

echo Layer built successfully!
echo Upload openai-layer.zip to AWS Lambda as a layer.