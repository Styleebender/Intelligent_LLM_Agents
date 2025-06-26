@echo off
echo Building OpenAI Agents Lambda layer with Docker...

REM Clean up any existing python directory
if exist python rmdir /s /q python
if exist openai-agents-layer.zip del openai-agents-layer.zip

REM Build the Docker image
echo Building Docker image (this may take a few minutes)...
docker build -t lambda-openai-agents-layer .

REM Create container and copy the layer contents
echo Extracting layer contents...
docker create --name temp-agents-container lambda-openai-agents-layer
docker cp temp-agents-container:/opt/python ./python
docker rm temp-agents-container

REM Create the zip file for Lambda layer
echo Creating zip file...
powershell Compress-Archive -Path python -DestinationPath openai-agents-layer.zip -Force

echo OpenAI Agents layer built successfully!
echo Upload openai-agents-layer.zip to AWS Lambda as a layer.
pause