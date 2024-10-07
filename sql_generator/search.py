from fuzzywuzzy import fuzz
from util import Util as util
from abc import ABC, abstractmethod
import pandas as pd
from db import DBMetadata, IDBConnection
import pickle
from enum import Enum

class SearchTypes(Enum):
    ELASTICSEARCH = 1
    FUZZY_SEARCH = 2


class ISearch(ABC):
    config: any
    db_conn: IDBConnection
    def __init__(self, config_path: str='', **kwargs):     
        try:
            if config_path != '':
                self.config = util.load_yaml_config(config_path)  
            if 'db_conn' in kwargs:
                self.db_conn = kwargs['db_conn']
        except Exception as e:
            print(f"Error loading Search config: {e}")

    @abstractmethod
    def search_by_query(self, query: str,  **kwards) -> list:   
        pass     

    @abstractmethod
    def create_index(self, db_name: str, data: DBMetadata):
        pass

class Elasticsearch(ISearch):

    def create_index(self, db_name, data: DBMetadata):
        pass
    
    def search_by_query(self, db_name, query: str, **kwards):
        return []       



class FuzzySearch(ISearch):
    db_name: str = ''
    df_table_columns: pd.DataFrame = None
    pre_processor = None

    def create_index(self, db_name: str, data: DBMetadata):
        self.df_table_columns = data.df_table_columns
        if self.db_conn is None:
            raise ValueError("db_conn not provided.")
        self.db_conn.save_file(f"{db_name}_table_columns.pkl", pickle.dumps(self.df_table_columns))

    def search_by_query(self, db_name, query: str, **kwards):
        if self.pre_processor is None:
            import preprocessor
            from preprocessor import pre_processor
            self.pre_processor = pre_processor
        if self.df_table_columns is None or db_name != self.db_name:
            if self.db_conn is None:
                raise ValueError("db_conn not provided.")
            print(f"Loading metadata for {db_name}")
            self.df_table_columns = pickle.loads(self.db_conn.load_file(f"{db_name}_table_columns.pkl"))
            self.db_name = db_name
            
        similarity_threshold = kwards.get('similarity_threshold', 90)
        max_synonyms = kwards.get('max_synonyms', 5)
        
        keywords = self.pre_processor.query_to_keywords(query, max_synonyms)
        tables = self.search_by_keywords(keywords, similarity_threshold)
        return tables
        
    def search_by_keywords(self, keywords: list, similarity_threshold=90):
        df_search = self.df_table_columns[
            self.df_table_columns.apply(
                self._match_table,
                axis=1,
                keywords=keywords,
                similarity_threshold=similarity_threshold
                )
            ]
        return df_search
        
    def _match_table(self, table_data: pd.Series, keywords: list, similarity_threshold: int):
        for keyword in keywords:
            if any(fuzz.partial_ratio(keyword, column) > similarity_threshold for column in table_data['column_name']):
                return True    
            elif fuzz.partial_ratio(keyword, table_data['table_name']) > similarity_threshold:
                return True
        return False
    
    
    
class SearchFactory:
    @staticmethod
    def get_search_provider(search_type: SearchTypes, **kwargs)-> ISearch:
        if search_type == SearchTypes.ELASTICSEARCH:
            config_path = kwargs.get('config_path', 'config/elasticsearch.yaml')
            return Elasticsearch(config_path)
        elif search_type == SearchTypes.FUZZY_SEARCH:
            db_conn = kwargs.get('db_conn', None)
            if db_conn is None:
                raise ValueError("db_conn not provided.")
            return FuzzySearch(config_path='', db_conn=db_conn)
        else:
            raise ValueError(f"Unknown Search type: {search_type}.")