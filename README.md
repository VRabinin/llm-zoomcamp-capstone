# Natural Language to SQL Translator

## Description
This project focuses on translating user's questions in natural language into SQL statements which can be executed on the database to get the desired answers. It leverages NLP techniques to understand and process user queries and generate the corresponding SQL code, and it was implemented for [LLM Zoomcamp 2024](https://github.com/DataTalksClub/llm-zoomcamp) - a free course about LLMs and RAG.

## Problem Statement
Many users, especially those without technical backgrounds, find it challenging to interact with databases using SQL. They often need to retrieve information from databases but lack the knowledge of SQL syntax and structure. This project aims to bridge that gap by allowing users to ask questions in natural language and get the corresponding SQL queries.

## Solution
Our application uses advanced Natural Language Processing (NLP) techniques to interpret user queries and translate them into SQL statements. Specifically, we leverage the Retrieval-Augmented Generation (RAG) technique with OpenAI's ChatGPT as our primary Large Language Model (LLM). However, the system is designed to be flexible and can connect to other Generative AI models as well.

For the retrieval component, users can choose between Elasticsearch and fuzzy search. The architecture is extensible, allowing for the addition of other search options as needed. This combination of LLM and retrieval techniques enables users to interact with databases using simple, everyday language, making data retrieval more accessible and efficient.

The frontend of the application is built using Streamlit, a popular framework for creating interactive web applications in Python.

## Technologies
- Python 3.11
- [Poetry](https://python-poetry.org/docs/) for Python dependency management 
- [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) for text search
- [Spacy] (https://spacy.io/usage/spacy-101) to extract keywords from user query
- [Gensim](https://radimrehurek.com/gensim/intro.html) for generating keyword synonyms
- Streamlit for the user interface
- Docker and Docker Compose for containerization
- PostgreSQL to run sample databases
- Grafana for monitoring and PostgreSQL as the backend for it
- OpenAI as an LLM

## Source Data
For testing purposes we use a couple of PostgreSQL sample databases
- [DVD Rentals](https://www.postgresqltutorial.com/postgresql-getting-started/postgresql-sample-database/) DVD rental database represents the business processes of a DVD rental store. 
- [Adventure Works](https://github.com/lorint/AdventureWorks-for-Postgres/) Microsoft sample database converted to PostgreSQL by Lorin Thwaits.

## Installation

### Preparation
Depending on the IDE you use, prepare the environment variables using the template file .env_template. In VS Code, it is enough to rename it into .env. You need to cehck and adjust at least the following environment variables
- POSTGRES_L_PORT. Port to expose PostgreSQL to localhost.
- DAGSTER_PORT. Port to expose Dagster to localhost.
- ELASTICSEARCH_PORT_9200. Port mapping to localhost for elasticsearch.
- ELASTICSEARCH_PORT_9300. Port mapping to localhost for elasticsearch.
- OPENAI_API_KEY. Holds your OpenAI API key for accessing LLM models. It is recommended to create a new project and use a separate key.

### Running using Docker Compose
Use Docker Compose to set up the environment:
    ```sh
    docker-compose -f docker/docker-compose.yaml up --detach
    ```

### Running the App and Dagster Pipeline locally
#### Preparation
To set up the project, follow these steps:
1. Prepare Virtual Environment with Python 3.11. You can use pyenv or venv module

2. Install Poetry:
    ```sh
    pip install poetry
    ```

3. Install project dependencies:
    ```sh
    poetry install
    ```
4. Download the necessary NLP model:
    ```sh
    python -m spacy download en_core_web_sm
    ```

5. Use Docker Compose to set up the PostgreSQL, Elasticsearch and Grafana:
    ```sh
    docker-compose -f docker/docker-compose.yaml up postgres postgres_init elasticsearch grafana --detach
    ```

#### Starting the application
1. Set sql_generator as current directory
    ```sh
    cd sql_generator
    ```

2. Run streamlit with the following parameters.
    ```sh
    POSTGRES_HOST=localhost POSTGRES_PORT=$POSTGRES_L_PORT streamlit run app.py --server.port=8501 --server.address=0.0.0.0
    ```
2. You can access Streamlit App by naviating to http://127.0.0.1:8501/

#### Starting Dagster
1. Run the following command from the main project folder. If port 3002 is occupied, replace '-p 3002' with the available port number.
    ```sh
    dagster dev -d sql_generator -p 3002 -f pipeline/repo.py
    ```
2. You can access dagster by naviating to `http://127.0.0.1:3002/`

## Usage
### Create indexes for text search
Before the first use, we need to run the pipeline to prepare indexes based on the database metadata.
1. Open Dagster in your browser: `http://127.0.0.1:3002/` (replace port number if needed)

2. Navigate to `etl_job` which is the only job in hte repository.

3. Go to `Launchpad` tab and hit the button `Launch Run` in the bottom-right corner.

4. Confirm successful ewxecution.

### Using the SQL Translator App

1. Access the application through your web browser at `http://localhost:8501` (replace port number if needed).

2. Enter your natural language query in the input field.

3. Choose the following parameters
- `Database` which you want to query.
- `LLM Model` which will generate SQL
- `Search Provider` to facilitate retrieval (only `Fuzzywuzzy` is implemented at the moment) 

3. The application will process your query and display the corresponding SQL statement.

### Monitoring
We use Grafana for monitoring the application. 
It's accessible at [localhost:3000](http://localhost:3000):

- Login: "admin"
- Password: "admin"

To initialize the dashboard, first ensure Grafana is running (it starts automatically when you do `docker-compose up`). Then start shell, navigate to the folder `monitoring` and run

    ```
    python grafana_init.py
    ```

## Sample Queries
Here are some sample queries for DVD Rental database to get you started:
- [Sample Queries](https://github.com/AadamBodunrin/SQL-for-Beginners/blob/master/DVDRental%20Database%20Queries.sql)


