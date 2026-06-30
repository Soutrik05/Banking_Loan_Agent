#!/bin/bash
# Build and test the Docker image locally
docker build -t loan-agent-backend .
docker run -p 8000:8000 --env-file .env loan-agent-backend
