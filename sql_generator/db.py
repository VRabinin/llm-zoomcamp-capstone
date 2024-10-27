import sqlalchemy, os
from typing import Optional, Dict, List
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from abc import ABC
from sqlalchemy import Engine, MetaData, create_engine, text, inspect
from sqlalchemy.sql import func as sql_func

TZ_INFO = os.getenv("TZ", "Europe/Berlin")
tz = ZoneInfo(TZ_INFO)

SUPPORTED_DB_TYPES = ["postgresql"]
EXCLUDED_DATABASES = ["postgres", "dagster", "sql_generator"]
SYSTEM_SCHEMAS = ["information_schema", "pg_catalog"]

# Database connection parameters

DATABASES_QUERY_POSTGRES = """
SELECT datname
FROM pg_database
WHERE datistemplate = false;
"""

COLUMNS_QUERY_POSTGRES = """
SELECT
    c.table_schema,
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
    ON c.table_catalog = t.table_catalog
    AND c.table_schema = t.table_schema
    AND c.table_name = t.table_name
WHERE c.table_schema <> 'information_schema' 
AND c.table_schema <> 'pg_catalog'
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
    src_metadata: MetaData
    df_table_columns: pd.DataFrame
        
class DBConnection:
    db_type: str
    db_name: str
    db_host: str
    db_port: str
    db_user: str
    db_password: str
    read_only: bool
    engine: Engine
    metadata: Dict[str, DBMetadata]

    def __init__(self, db_type: str, db_name: str, db_host: str, db_port: str, db_user: str, db_password: str, read_only: bool=True):
        self.db_type = db_type
        if db_type not in SUPPORTED_DB_TYPES:
            raise ValueError(f"Unsupported database type: {db_type}. Supported types are: {SUPPORTED_DB_TYPES}")
        self.main_db_name = db_name # Database which was used to create object.
        self.db_name = db_name #Current database, can be changed by set_curr_database method.
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.read_only = read_only
        self._init_engine()
        self._load_metadata()
    
    def _init_engine(self, db_name: Optional[str] = None):
        """
        Initializes the database engine with the provided or default database name.

        Args:
            db_name (Optional[str]): The name of the database to connect to. If not provided, 
                                     the default database name (`self.db_name`) will be used.

        Returns:
            None
        """

        if db_name is None:
            db_name = self.db_name
        self.engine = create_engine(f"{self.db_type}://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{db_name}")
        self.engine.update_execution_options(read_only=self.read_only)

    def get_curr_database(self):
        return self.db_name

    def get_metadata(self, refresh: bool=False, exclude_system_tables: bool=True)-> DBMetadata:
        if self.metadata.get(self.db_name) is None or refresh:
            self._load_metadata()
        return self.metadata[self.db_name] 

    def _load_metadata(self):
        if not hasattr(self, 'metadata'):
            self.metadata = {}
        # Skip loading metadata if it was already loaded, no inline refresh implemented.
        if self.metadata.get(self.db_name) is not None:
            return
        # Initialize the engine database name changed
        if self.db_name != self.engine.url.database:
            self._init_engine(self.db_name)
        db_md = DBMetadata()
        db_md.src_metadata = MetaData()
        inspector = inspect(self.engine)    
        for schema in inspector.get_schema_names():
            if schema in SYSTEM_SCHEMAS:
                continue
            db_md.src_metadata.reflect(bind=self.engine, schema=schema, views=True)
            # Get Tables/Columns metadata
            tables = db_md.src_metadata.tables
            tab_output = []
            for table in tables:
                tab_output.append({
                    'table_schema': tables[table].schema if tables[table].schema else '',
                    'table_name': tables[table].name,
                    'table_type': tables[table].info.get('type', 'table'),
                    'column_name': list(tables[table].columns.keys()),
                    'data_type': [str(tables[table].columns[col].type) for col in tables[table].columns.keys()],
                    'is_primary_key': [col.primary_key for col in tables[table].columns.values()],
                    'is_nullable': [col.nullable for col in tables[table].columns.values()]
                })
                #tab_col = tables[table].schema \
                #    + '.' if tables[table].schema else '' \
                #    + tables[table].name \
                #    + ' (' \
                #    + ', '.join(tables[table].columns.keys())\
                #    + ')'
                #db_md.table_columns.append(tab_col)
            # Add currewnt DB metadata to the dictionary
        db_md.df_table_columns = pd.DataFrame(tab_output, columns=['table_schema', 'table_name', 'table_type', 'column_name', 'data_type', 'is_primary_key', 'is_nullable'])
        self.metadata[self.db_name] = db_md

    def set_curr_database(self, db_name: str):
        if self.db_name == db_name:
            return
        self.db_name = db_name
        if self.engine is not None:
            self.engine.dispose()
        self._init_engine()
        self._load_metadata()

    def execute_sql(self, query: str) -> pd.DataFrame:
        """
        Executes a given SQL query and returns the fetched data.
        Args:
            query (str): The SQL query to be executed.
        Returns:
            list: A list of tuples containing the rows fetched by the query.
        """
        try:
            with self.engine.connect() as con:
                cursor = con.execute(text(query))     
                data = cursor.fetchall()
                # Get column names from the cursor description
                column_names = cursor.keys()
                #if column_names[0] == 'error':
                #    self.conn.close()
                #    self.conn = self._init_conn()                 
            #cursor.close()
        except Exception as e:
            data = [str(e)]
            column_names = ['error']
            #self.conn.close()
            #self.conn = self._init_conn()    
                
        # Create DataFrame with the fetched data and column names
        return pd.DataFrame(data, columns=column_names)

    def _get_database_list_postgres(self) -> list:
        with self.engine.connect() as con:
            cursor = con.execute(text(DATABASES_QUERY_POSTGRES))
            df_databases = pd.DataFrame(cursor.fetchall())
            return df_databases.iloc[:,0].tolist()

    def get_database_list(self) -> list:
        """
        Retrieves a list of databases based on the database type.
        This method dynamically calls a private method specific to the database type
        to get the list of databases. The private method should be named in the format
        `_get_database_list_<db_type>`.
        Returns:
            pd.DataFrame: A DataFrame containing the list of databases.
        """
        match self.engine.dialect.name:
            case "postgresql":
                db_list = self._get_database_list_postgres()
            case _:
                raise ValueError(f"Unsupported database type: {self.engine.dialect.name}")
        return [db for db in db_list if db not in EXCLUDED_DATABASES]
            
            

    def save_file(self, file_name: str, file_data):
        temp_db_name = ''         
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            self._init_engine()
        try:        
            try:    
                with self.engine.connect() as con:
                    # Delete the file if it already exists        
                    con.execute(text(f"DELETE FROM files WHERE file_name = '{file_name}'"))
                    #data = sql_func.HEX(file_data)
                    #print(data)
                    # Execute the INSERT statement 
                    con.execute(text(f"INSERT INTO files\
                        (file_name, file_data)\
                        VALUES(:file_name, :file_data)"), {'file_name': file_name, 'file_data': file_data})
                    # Commit the changes to the database 
                    con.commit() 
            except (Exception) as error: 
                print("Error while inserting data in files table", error) 
            finally: 
                pass
        finally: 
            if temp_db_name != '':
                self.db_name = temp_db_name
                self._init_engine()                
        
    def load_file(self, file_name: str): 
        temp_db_name = '' 
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            self._init_engine() 
        data = None        
        try:            
            with self.engine.connect() as con:                
                cursor = con.execute(text(f"SELECT file_data FROM files WHERE file_name = '{file_name}'"))
                data = cursor.fetchone()[0]
                # print(data)
        except (Exception) as error: 
            print("Error reading data from files table", error) 
        finally: 
            if temp_db_name != '':
                self.db_name = temp_db_name
                self._init_engine()              
        return data

    def save_conversation(self, conversation_id, question, answer_data, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(tz)
        temp_db_name = '' 
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            self._init_engine()  
        try:
            print(answer_data)
            with self.engine.connect() as con:  
                con.execute(text(
                    """
                    INSERT INTO conversations 
                    (id, question, answer, database_name, model, search_provider, rag_parameters, response_time, relevance, 
                    relevance_explanation, prompt_tokens, completion_tokens, total_tokens, 
                    eval_prompt_tokens, eval_completion_tokens, eval_total_tokens, llm_cost, timestamp)
                    VALUES (:v1, :v2, :v3, :v4, :v5, :v6, :v7, :v8, :v9, :v10, :v11, :v12, :v13, :v14, :v15, :v16, :v17, :v18)
                    """), {
                        'v1': conversation_id,
                        'v2': question,
                        'v3': answer_data["answer"],
                        'v4': answer_data["database_name"],                        
                        'v5': answer_data["model"],
                        'v6': answer_data["search_provider"],
                        'v7': answer_data["rag_parameters"],                        
                        'v8': answer_data["response_time"],
                        'v9': answer_data["relevance"],
                        'v10': answer_data["relevance_explanation"],
                        'v11': answer_data["prompt_tokens"],
                        'v12': answer_data["completion_tokens"],
                        'v13': answer_data["total_tokens"],
                        'v14': answer_data["eval_prompt_tokens"],
                        'v15': answer_data["eval_completion_tokens"],
                        'v16': answer_data["eval_total_tokens"],
                        'v17': answer_data["llm_cost"],
                        'v18': timestamp
                })
                con.commit()
        finally:
            if temp_db_name != '':
                self.db_name = temp_db_name
                self._init_engine()


    def save_feedback(self, conversation_id, feedback, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(tz)
        temp_db_name = '' 
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            self._init_engine() 
        try:
            with self.engine.connect() as con:  
                con.execute(text(
                    f"DELETE FROM feedback WHERE conversation_id='{conversation_id}'"))
                con.execute(text(
                    """INSERT INTO feedback (conversation_id, feedback, timestamp) VALUES (:v1, :v2, COALESCE(:v3, CURRENT_TIMESTAMP))"""),
                    {'v1': conversation_id, 'v2': feedback, 'v3': timestamp}
                )
                con.commit()            
        finally:
            if temp_db_name != '':
                self.db_name = temp_db_name
                self._init_engine()  

           