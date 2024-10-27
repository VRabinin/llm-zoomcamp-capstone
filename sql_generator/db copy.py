import psycopg2, os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from abc import ABC, abstractmethod
from psycopg2.extensions import connection

TZ_INFO = os.getenv("TZ", "Europe/Berlin")
tz = ZoneInfo(TZ_INFO)

SUPPORTED_DB_TYPES = ["postgres"]
EXCLUDED_DATABASES = ["postgres", "dagster", "sql_generator"]

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
    df_columns: pd.DataFrame
    df_table_columns: pd.DataFrame    
    df_fk: pd.DataFrame
    df_table_view: pd.DataFrame

class IDBConnection(ABC):
    db_name: str
    metadata: DBMetadata 
    
    def __init__(self, db_name):
        self.db_type = db_name
    
    @abstractmethod
    def get_database_list(self) -> list:
        pass

    @abstractmethod
    def execute_sql(self, query: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def set_curr_database(self, db_name):
        pass

    def get_curr_database(self):
        return self.db_name

    @abstractmethod
    def _load_metadata(self):
        pass

    def get_metadata(self)-> DBMetadata:
        return self.metadata
    
    @abstractmethod
    def save_file(self, file_name: str, file_data):
        pass

    @abstractmethod
    def load_file(self, file_name: str):
        pass    

    @abstractmethod
    def save_feedback(self, conversation_id, feedback, timestamp=None):
        pass
    
    @abstractmethod
    def save_conversation(self, conversation_id, question, answer_data, timestamp=None):
        pass
        
class PostgresConnection(IDBConnection):
    db_name: str
    db_host: str
    db_port: str
    db_user: str
    db_password: str
    read_only: bool
    conn: connection

    
    def __init__(self, db_name, db_host, db_port, db_user, db_password, read_only=True):
        super().__init__("postgres")
        self.main_db_name = db_name # Database which was used to create object.
        self.db_name = db_name #Current database, can be changed by set_curr_database method.
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.read_only = read_only
        self.conn = self._init_conn()
        self._load_metadata()
        
    def _init_conn(self):
        conn = psycopg2.connect(
            database=self.db_name,
            user=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port
        )
        if self.read_only:
            conn.set_session(readonly=True)
        else:
            conn.set_session(readonly=False)
        return conn
    
    def _load_metadata(self):
        #Get Tables/Columns metadata
        
        self.metadata = DBMetadata()
        
        cursor = self.conn.cursor()
        cursor.execute(COLUMNS_QUERY_POSTGRES)
        columns_data = cursor.fetchall()        
        cursor.close()
        columns = ['table_schema', 'table_name', 'table_type', 'column_name', 'column_data_type', 'is_primary_key', 'is_nullable']
        self.metadata.df_columns = pd.DataFrame(columns_data, columns=columns)
        self.metadata.df_columns['table_name'] = self.metadata.df_columns[['table_schema', 'table_name']]\
            .agg('.'.join, axis=1)\
            .drop(columns=['table_schema'])
        # Create a DataFrame with table name and a list of all table columns in a single field
        self.metadata.df_table_columns = self.metadata.df_columns\
            .groupby('table_name')['column_name'].apply(list).reset_index()
        cursor = self.conn.cursor()
        cursor.execute(FK_QUERY_POSTGRES)
        fk_data = cursor.fetchall()
        cursor.close()        
        columns = ['source_table', 'source_column', 'target_table', 'target_column']
        self.metadata.df_fk = pd.DataFrame(fk_data, columns=columns)

        cursor = self.conn.cursor()
        cursor.execute(TABLE_VIEW_QUERY_POSTGRES)
        table_view_data = cursor.fetchall()
        cursor.close()        
        table_view_columns = ['view_name', 'table_name']
        self.metadata.df_table_view = pd.DataFrame(table_view_data, columns=table_view_columns)

    def set_curr_database(self, db_name: str):
        if self.db_name == db_name:
            return
        
        self.db_name = db_name
        if self.conn is not None:
            self.conn.close()
        self.conn = self._init_conn()
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
            cursor = self.conn.cursor()
            cursor.execute(query)
            data = cursor.fetchall()
            # Get column names from the cursor description
            column_names = [desc[0] for desc in cursor.description]
            if column_names[0] == 'error':
                self.conn.close()
                self.conn = self._init_conn()                 
            #cursor.close()
        except Exception as e:
            data = [str(e)]
            column_names = ['error']
            self.conn.close()
            self.conn = self._init_conn()    
                
        # Create DataFrame with the fetched data and column names
        return pd.DataFrame(data, columns=column_names)

    def get_database_list(self) -> list:
        """
        Retrieves a list of databases based on the database type.
        This method dynamically calls a private method specific to the database type
        to get the list of databases. The private method should be named in the format
        `_get_database_list_<db_type>`.
        Returns:
            pd.DataFrame: A DataFrame containing the list of databases.
        """
        cursor = self.conn.cursor()
        cursor.execute(DATABASES_QUERY_POSTGRES)
        df_databases = pd.DataFrame(cursor.fetchall())
        cursor.close()
        df_databases = df_databases[~df_databases[0].isin(EXCLUDED_DATABASES)]
        
        return df_databases[0].tolist()

    def save_file(self, file_name: str, file_data):
        temp_db_name = ''         
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            if self.conn is not None:
                self.conn.close()
            self.conn = self._init_conn()             
        try:        
            cursor = self.conn.cursor()
            try:            
                cursor.execute("DELETE FROM files WHERE file_name = %s", (file_name,))
                # Execute the INSERT statement 
                cursor.execute("INSERT INTO files\
                (file_name, file_data) " +
                        "VALUES(%s,%s)", 
                        (file_name, psycopg2.Binary(file_data))) 
                # Commit the changes to the database 
                self.conn.commit() 
                cursor.close()
            except (Exception, psycopg2.DatabaseError) as error: 
                print("Error while inserting data in files table", error) 
            finally: 
                pass
        finally: 
            if temp_db_name != '':
                self.db_name = temp_db_name
                self.conn = self._init_conn()                
        
    def load_file(self, file_name: str): 
        temp_db_name = '' 
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            if self.conn is not None:
                self.conn.close()
            self.conn = self._init_conn()   
        data = None        
        try: 
            cursor = self.conn.cursor()
            try:            
                cursor.execute("SELECT file_data FROM files WHERE file_name = %s", (file_name,))
                data = cursor.fetchone()[0]
                print(data)
                cursor.close()
            except (Exception, psycopg2.DatabaseError) as error: 
                print("Error reading data from files table", error) 
            finally: 
                pass
        finally: 
            if temp_db_name != '':
                self.db_name = temp_db_name
                self.conn = self._init_conn()               
        return data

    def save_conversation(self, conversation_id, question, answer_data, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(tz)
        temp_db_name = '' 
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            if self.conn is not None:
                self.conn.close()
            self.conn = self._init_conn()  
        try:
            print(answer_data)
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations 
                    (id, question, answer, database_name, model, search_provider, rag_parameters, response_time, relevance, 
                    relevance_explanation, prompt_tokens, completion_tokens, total_tokens, 
                    eval_prompt_tokens, eval_completion_tokens, eval_total_tokens, llm_cost, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conversation_id,
                        question,
                        answer_data["answer"],
                        answer_data["database_name"],                        
                        answer_data["model"],
                        answer_data["search_provider"],
                        answer_data["rag_parameters"],                        
                        answer_data["response_time"],
                        answer_data["relevance"],
                        answer_data["relevance_explanation"],
                        answer_data["prompt_tokens"],
                        answer_data["completion_tokens"],
                        answer_data["total_tokens"],
                        answer_data["eval_prompt_tokens"],
                        answer_data["eval_completion_tokens"],
                        answer_data["eval_total_tokens"],
                        answer_data["llm_cost"],
                        timestamp
                    ),
                )
            self.conn.commit()
        finally:
            if temp_db_name != '':
                self.db_name = temp_db_name
                self.conn = self._init_conn()   


    def save_feedback(self, conversation_id, feedback, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(tz)
        temp_db_name = '' 
        if self.db_name != self.main_db_name:
            temp_db_name = self.db_name
            self.db_name = self.main_db_name 
            if self.conn is not None:
                self.conn.close()
            self.conn = self._init_conn()  
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM feedback WHERE conversation_id='{conversation_id}'")
                cur.execute(
                    """INSERT INTO feedback (conversation_id, feedback, timestamp) VALUES (%s, %s, COALESCE(%s, CURRENT_TIMESTAMP))""",
                    (conversation_id, feedback, timestamp),
                )
            self.conn.commit()            
        finally:
            if temp_db_name != '':
                self.db_name = temp_db_name
                self.conn = self._init_conn()   

class DBConnectionFactory:
    @staticmethod
    def get_db_connection(db_type: str, **kwargs)-> IDBConnection:
        if db_type == "postgres":
            db_name = kwargs.get("db_name")
            db_host = kwargs.get("db_host")
            db_port = kwargs.get("db_port")
            db_user = kwargs.get("db_user")
            db_password = kwargs.get("db_password")
            read_only = kwargs.get("read_only", True)
            if db_name is None or db_host is None or db_user is None or db_password is None:
                raise ValueError("Database connection parameters are missing.")
            return PostgresConnection(db_name, db_host, db_port, db_user, db_password, read_only)
        else:
            raise ValueError(f"Unknown database type: {db_type}. Only 'postgres' is supported.")