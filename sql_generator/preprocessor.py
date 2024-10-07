from spacy.language import Language
from inflect import engine as inflect_engine
from gensim.models import KeyedVectors
import gensim.downloader as gensim_api
from util import Util as util
import os
import spacy


PREPROCESSOR_CONFIG_PATH  = 'config/preprocessor.yaml'

#@singleton
class PreProcessor:
    spacy: Language
    inflect: inflect_engine
    word_vectors: KeyedVectors
    models: list
    
    def __init__(self, config_path=PREPROCESSOR_CONFIG_PATH):
        #pp_config = util.load_yaml_config(config_path)
        self.models = []
        #for model in pp_config['gensim_models']:
        #    self.models.append(model['name'])
        self.models = ['glove-wiki-gigaword-50', 'glove-wiki-gigaword-100', 'glove-wiki-gigaword-200', 'glove-wiki-gigaword-300']
        self.spacy = spacy.load("en_core_web_sm")
        self.inflect = inflect_engine()
        self.word_vectors = gensim_api.load(self.models[0])

    def get_gensim_models(self)->list:
        return self.models

    def set_gensim_model(self, model_name: str):
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found in available models: {self.models}")
        self.word_vectors = gensim_api.load(model_name)

    def extract_keywords(self, query: str):
        doc = self.spacy(query)
        keywords = [token.text for token in doc if token.pos_ in ["NOUN", "PROPN", "NUM"]]
        keywords_final = keywords.copy()
        for keyword in keywords:
            if self.inflect.singular_noun(keyword):  # Returns singular form if plural
                word = self.inflect.singular_noun(keyword)
                keywords_final.append(word)
            else:
                word = keyword
        #print(keywords_final)
        return keywords_final
    
    def generate_synonyms(self, word: str, max_synonyms=5):
        if max_synonyms < 1:
            return []
        #print(f"Generating synonyms for: {word}")
        if self.word_vectors.has_index_for(word):
            #token_vector = model.wv[token]            
            synonym_tuples = self.word_vectors.most_similar(positive=[word], negative=[], topn=max_synonyms)
            synonyms = [synonym[0] for synonym in synonym_tuples]
            return synonyms
        else: 
            # Get embedding for the target word
            return []

    def query_to_keywords(self, query: str, max_synonyms=5):
        keywords = pre_processor.extract_keywords(query)
        keywords_final = keywords.copy()
        for word in keywords:
            synonyms = pre_processor.generate_synonyms(word, max_synonyms)
            keywords_final.extend(synonyms)
        keywords_final = list(set(keywords_final))
        return keywords_final

pre_processor = PreProcessor(PREPROCESSOR_CONFIG_PATH)
