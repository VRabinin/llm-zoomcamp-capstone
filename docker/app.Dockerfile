FROM python:3.12-slim

RUN apt-get update --allow-insecure-repositories
#RUN apt-get install libpq-dev -y
#RUN apt-get install python3-dev -y
RUN apt-get install gcc -y --allow-unauthenticated
RUN apt-get install g++ -y --allow-unauthenticated

WORKDIR /app

ENV POETRY_VIRTUALENVS_CREATE=false

#RUN pip3.12 install --no-cache-dir poetry
RUN pip3.12 install poetry

RUN mkdir -p /app/data/llama_text_to_sql_dataset/

COPY data/llama_text_to_sql_dataset /app/data/llama_text_to_sql_dataset

COPY ["pyproject.toml", "poetry.lock", "./"]

RUN poetry install

RUN poetry run python -m spacy download en_core_web_sm

ARG CACHE_DATE=not_set

COPY sql_generator .

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Define environment variable
ENV STREAMLIT_SERVER_PORT=8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]