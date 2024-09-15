FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry

RUN mkdir -p /app/data/llama_text_to_sql_dataset/

COPY data/llama_text_to_sql_dataset /app/data/llama_text_to_sql_dataset
COPY ["pyproject.toml", "poetry.lock", "./"]

RUN poetry install

COPY sql_generator .

EXPOSE 5001

#CMD gunicorn --bind 0.0.0.0:5000 app:app