#!/bin/bash

# Stop and remove the sql-generator-app container
#docker-compose -f docker/docker-compose.yaml stop sql-generator-app
docker-compose -f docker/docker-compose.yaml rm -f -s dagster


# Rebuild the Docker image for sql-generator-app
docker-compose -f docker/docker-compose.yaml build --build-arg CACHE_DATE="$(date +%Y-%m-%d:%H:%M:%S)" dagster

# Start the sql-generator-app container
docker-compose -f docker/docker-compose.yaml up -d dagster