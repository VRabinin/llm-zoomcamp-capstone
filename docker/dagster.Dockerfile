FROM python:3.10-slim

RUN mkdir -p /opt/dagster/dagster_home /opt/dagster/app

RUN pip install dagster-webserver dagster-postgres dagster-aws fuzzywuzzy transformers torch scikit-learn

ARG CACHE_DATE=not_set
# Copy your code and workspace to /opt/dagster/app
COPY pipeline/repo.py pipeline/workspace.yaml pipeline/requirements.txt /opt/dagster/app/
COPY sql_generator /opt/dagster/app/
# Set the environment variable DAGSTER_HOME to /opt/dagster/dagster_home/
ENV DAGSTER_HOME=/opt/dagster/dagster_home/

# Copy dagster instance YAML to $DAGSTER_HOME
COPY pipeline/dagster.yaml /opt/dagster/dagster_home/
# Set the working directory
WORKDIR /opt/dagster/app
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3000

ENTRYPOINT ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000"]