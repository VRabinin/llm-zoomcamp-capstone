import os, psycopg2, spacy
import pandas as pd
from fuzzywuzzy import fuzz
# Database connection parameters

COLUMNS_QUERY_POSTGRES = """
SELECT 
    c.table_name, 
    CASE 
        WHEN t.table_type = 'BASE TABLE' THEN 'table'
        WHEN t.table_type = 'VIEW' THEN 'view'
    END AS table_type,    
    c.column_name, 
    c.data_type, 
    CASE 
        WHEN c.column_name IN (
            SELECT kcu.column_name
            FROM information_schema.table_constraints tco
            JOIN information_schema.key_column_usage kcu 
                ON kcu.constraint_name = tco.constraint_name
            WHERE tco.constraint_type = 'PRIMARY KEY' AND kcu.table_name = c.table_name
        ) THEN TRUE ELSE FALSE 
    END AS is_primary_key,
    c.is_nullable
FROM information_schema.columns c
JOIN information_schema.tables t
    ON c.table_name = t.table_name
WHERE c.table_schema = 'public'
ORDER BY c.table_name, c.column_name;
"""

FK_QUERY_POSTGRES = """
SELECT
    tc.table_name AS source_table,
    kcu.column_name AS source_column,
    ccu.table_name AS target_table,
    ccu.column_name AS target_column
FROM
    information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_schema = 'public';
"""

TABLE_VIEW_QUERY_POSTGRES = """
SELECT
    c1.relname AS view_name,
    c2.relname AS table_name
FROM
    pg_catalog.pg_depend d
    JOIN pg_catalog.pg_rewrite r ON d.objid = r.oid
    JOIN pg_catalog.pg_class c1 ON r.ev_class = c1.oid
    JOIN pg_catalog.pg_class c2 ON d.refobjid = c2.oid
WHERE
    c1.relkind = 'v' AND c2.relkind = 'r'
"""

class DBMetadata:
    def __init__(self, db_type, db_name, db_host, db_port, db_user, db_password):
        self.db_name = db_name
        self.db_type = db_type
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.spacy = spacy.load("en_core_web_sm")
        
        if self.db_type == "postgres":
            self.conn = self.__init_postgres()
            self.__load_metadata_postgres()
        else:
            raise ValueError(f"Unknown database type: {self.db_type}. Only 'postgres' is supported.")
        
    def __init_postgres(self):
        conn = psycopg2.connect(
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port
        )    
        return conn
    
    def __load_metadata_postgres(self):
        #Get Tables/Columns metadata
        cursor = self.conn.cursor()
        cursor.execute(COLUMNS_QUERY_POSTGRES)
        columns_data = cursor.fetchall()        
        cursor.close()
        columns = ['table_name', 'table_type', 'column_name', 'column_data_type', 'is_primary_key', 'is_nullable']
        self.df_columns = pd.DataFrame(columns_data, columns=columns)
        # Create a DataFrame with table name and a list of all table columns in a single field

        self.df_table_columns = self.df_columns.groupby('table_name')['column_name'].apply(list).reset_index()
        
        cursor = self.conn.cursor()
        cursor.execute(FK_QUERY_POSTGRES)
        fk_data = cursor.fetchall()
        cursor.close()        
        columns = ['source_table', 'source_column', 'target_table', 'target_column']
        self.df_fk = pd.DataFrame(fk_data, columns=columns)

        
        cursor = self.conn.cursor()
        cursor.execute(TABLE_VIEW_QUERY_POSTGRES)
        table_view_data = cursor.fetchall()
        cursor.close()        
        table_view_columns = ['view_name', 'table_name']
        self.df_table_view = pd.DataFrame(table_view_data, columns=table_view_columns)

    def search_by_query(self, query: str):
        doc = self.spacy(query)
        keywords = [token.text for token in doc if token.pos_ in ["NOUN", "PROPN", "NUM"]]
        return self.search_by_keywords(keywords)
        
    def search_by_keywords(self, keywords: list, similarity_threshold=90):
        df_search = self.df_table_columns[
            self.df_table_columns.apply(
                self.__match_table,
                axis=1,
                keywords=keywords,
                similarity_threshold=similarity_threshold
                )
            ]
        return df_search
        
    def __match_table(self, table_data: pd.Series, keywords: list, similarity_threshold: int):
        for keyword in keywords:
            if any(fuzz.partial_ratio(keyword, column) > similarity_threshold for column in table_data['column_name']):
                return True    
            elif fuzz.partial_ratio(keyword, table_data['table_name']) > similarity_threshold:
                return True
        return False
        
