import os
import pandas as pd
from datasets import load_from_disk

import minsearch
import yaml


DATA_PATH = os.getenv("DATA_PATH", "../data/llama_text_to_sql_dataset")
CONFIG_DIR = "config/"


class Index:
    def __init__(self, data_path=DATA_PATH, engine="minsearch", *args, **kwargs) -> None:
        """
        Initializes the index utility with the specified search engine.
        Args:
            data_path (str): The path to the data directory. Defaults to DATA_PATH.
            engine (str): The search engine to use. Can be "minsearch" or "elasticsearch". Defaults to "minsearch".
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        Raises:
            ValueError: If an unknown engine is specified.
        """
        
        self.engine = engine
        if self.engine == "minsearch":
            self.index = self.__load_minsearch_index(data_path, **kwargs)        
        elif self.engine == "elasticsearch":
            self.index = self.__load_elasticsearch_index(data_path, **kwargs)
        else:
            raise ValueError(f"Unknown engine: {engine}")

    def search(self, query, top_k=5, *args, **kwargs):
        """
        Search for a query using the specified search engine.
        Args:
            query (str): The search query.
            top_k (int, optional): The number of top results to return. Defaults to 5.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        Keyword Args:
            filter_dict (dict, optional): A dictionary of filters to apply (used only for 'minsearch' engine).
            boost_dict (dict, optional): A dictionary of boost parameters (used only for 'minsearch' engine).
        Returns:
            list: A list of search results.
        Raises:
            ValueError: If the search engine is unknown.
        """
        
        if self.engine == "minsearch":
            filet_dict = kwargs.get("filter_dict", {})
            boost_dict = kwargs.get("boost_dict", {})  
            return self.index.search(query, filet_dict, boost_dict, top_k)
        elif self.engine == "elasticsearch":
            return self.index.search(query, top_k)
        else:
            raise ValueError(f"Unknown engine: {self.engine}")


    def __load_minsearch_index(self, data_path=DATA_PATH, **kwargs):
        """
        Load and fit a MinSearch index from a dataset stored on disk.
        This method loads a dataset from the specified data path, converts it to a pandas DataFrame,
        and then to a list of dictionaries. It reads the configuration for the MinSearch index from
        a YAML file and fits the index using the documents from the dataset.
        Args:
            data_path (str): The path to the dataset to be loaded. Defaults to DATA_PATH.
            **kwargs: Additional keyword arguments.
        Returns:
            minsearch.Index: The fitted MinSearch index.
        """
        
        src_dataset = load_from_disk(data_path)
        df_dataset = src_dataset.to_pandas()
        documents = df_dataset.to_dict(orient="records")
        config_path = os.path.join(CONFIG_DIR, f"{self.engine}.yaml")
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        index = minsearch.Index(
            text_fields=config["text_fields"],
            keyword_fields=config["keyword_fields"],
        )
        index.fit(documents)
        return index
    
    
    def __load_elasticsearch_index(self, data_path=DATA_PATH, **kwargs):
        pass