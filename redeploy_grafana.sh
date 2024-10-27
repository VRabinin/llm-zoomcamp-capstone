#!/bin/bash

# Stop and remove the sql-generator-app container
#docker-compose -f docker/docker-compose.yaml stop sql-generator-app
docker-compose -f docker/docker-compose.yaml rm -f -s grafana

# Start the sql-generator-app container
docker-compose -f docker/docker-compose.yaml up -d grafana