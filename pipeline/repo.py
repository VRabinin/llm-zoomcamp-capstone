# repo.py
from dagster import job, op, repository
import psycopg2, os
from elasticsearch import Elasticsearch
from db import DBConnectionFactory
from search import SearchFactory, SearchTypes


@op
def extract_data_from_postgresql(context):
    #print("Connecting to PostgreSQL")
    #print(os.getenv("DAGSTER_PG_DB"))
    #print(os.getenv("DAGSTER_PG_USERNAME"))
    #print(os.getenv("DAGSTER_PG_PASSWORD"))
    #print(os.getenv("DAGSTER_PG_HOST"))
    #print(os.getenv("DAGSTER_PG_PORT"))
    db_conn = DBConnectionFactory.\
        get_db_connection(\
            db_type='postgres',
            db_name = 'dagster',
            db_host = os.getenv("DAGSTER_PG_HOST"),
            db_port = os.getenv("DAGSTER_PG_PORT"), 
            db_user = os.getenv("DAGSTER_PG_USERNAME") ,
            db_password = os.getenv("DAGSTER_PG_PASSWORD")
    )    
    #print("Connected to PostgreSQL")

    db_list = db_conn.get_database_list()

    db_metadata_all = {}

    for db_name in db_list:
        db_conn.set_curr_database(db_name)
        df_db_metadata = db_conn.get_metadata()
        db_metadata_all[db_name] = df_db_metadata

    return db_metadata_all 

@op
def load_data_into_elasticsearch(context, data):
#    es = Elasticsearch([{'host': 'elasticsearch', 'port': 9200}])
#    for record in data:
#        es.index(index='my_index', body=record)
    pass

@op
def load_data_into_fuzzy_search(context, data):
    db_conn = DBConnectionFactory.\
        get_db_connection(\
            db_type='postgres',
            db_name = 'sql_generator',
            db_host = os.getenv("DAGSTER_PG_HOST"),
            db_port = os.getenv("DAGSTER_PG_PORT"), 
            db_user = os.getenv("DAGSTER_PG_USERNAME"),
            db_password = os.getenv("DAGSTER_PG_PASSWORD"),
            read_only=False
    )   

    my_search = SearchFactory.get_search_provider(SearchTypes.FUZZY_SEARCH, db_conn=db_conn)

    for key, value in data.items():
        my_search.create_index(key, value)

@job
def etl_job():
    data = extract_data_from_postgresql()
    load_data_into_elasticsearch(data)
    load_data_into_fuzzy_search(data)    

@repository
def my_repository():
    return [etl_job]