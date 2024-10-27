from openai import OpenAI
import os
from index import Index
from util import Util as util

from abc import ABC, abstractmethod


class ILlmProvider(ABC):
    config: dict
    provider_name: str
    
    def __init__(self, provider_name, config: dict) -> None:
        self.config = config
        self.provider_name = provider_name
    
    @abstractmethod
    def prompt(self, model_name: str, prompt: str):
        pass
    
    def get_provider_name(self):
        return self.provider_name

class PromptGenerator:
    def __init__(self, templates_path: str):
        self.templates = {}
        for subdir, dirs, files in os.walk(f"./{templates_path}"):
            for file_name in files:
                if file_name.endswith(".txt"):
                    template_name = os.path.splitext(file_name)[0]
                    file_path = f"{templates_path}/{file_name}"
                    with open(file_path, 'r') as file:
                        self.templates[template_name] = file.read()
    
    def get_template_list(self):
        return list(self.templates.keys())
    
    def get_prompt(self, template_name: str, **kwargs):
        prompt_template = self.templates.get(template_name) 
        return str(prompt_template).format(**kwargs) 

class LLM:
    #prompt_gen: PromptGenerator
    llm: ILlmProvider
    llm_settings: dict = {}
    
    def __init__(self, config_path):
        try:
            llm_config = util.load_yaml_config(config_path)
            for provider in llm_config['providers']:
                for model in provider['models']:
                    self.llm_settings[f"{provider['name']}: {model['name']}"] = {
                        "provider_name": provider['name'],
                        "provider_class": provider['class'],
                        "provider_params": provider['params'],
                        "model": model 
                    }       
        except Exception as e:
            print(f"Error loading LLM config: {e}")
        self.llm = None

    def get_model_list(self):
        return list(self.llm_settings.keys())

    def prompt(self, model_id, prompt):
        requested_model = self.llm_settings.get(model_id)
        if requested_model is None:
            raise ValueError(f"Model config for {model_id} not found")
        try:
            if self.llm is None:
                self.llm = eval(requested_model['provider_class'])(
                    requested_model['provider_name'],
                    requested_model['provider_params']
                )
            elif self.llm.get_provider_name() != requested_model['provider_name']:
                self.llm = eval(requested_model['provider_class'])(
                    requested_model['provider_name'],
                    requested_model['provider_params']
                )
        except Exception as e:
            print(f"Error loading LLM provider: {e}")
        
        return self.llm.prompt(requested_model['model'], prompt)
  
    
class OpenAIProvider(ILlmProvider):
    llm: OpenAI = None

    def __init__(self, provider_name, config: dict):
        super().__init__(provider_name, config)    
        try:
            api_key = config['api_key']
        except Exception as e:
            print(config)
            print(f"Error loading OpenAI config: API key not found")
        self.llm = OpenAI(api_key=api_key)

    def prompt(self, model_id, prompt):
        model = model_id['name']
        print(model + prompt)

        response = self.llm.chat.completions.create(
            model=model,
            messages=[
                #{
                #    "role": "system",
                #    "content": "You are a helpful assistant."
                #},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        answer = response.choices[0].message.content
        token_stats = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,   
        }
        relevance = {}
        rel_token_stats = {}
        llm_cost = self._get_cost(token_stats, 
                                  model_id['prompt_token_cost_per_1000'], 
                                  model_id['output_token_cost_per_1000'])
        answer_data = {
            "answer": answer,
            "model": model,
            "relevance": relevance.get("Relevance", "UNKNOWN"),
            "relevance_explanation": relevance.get(
                "Explanation", "Failed to parse evaluation"
            ),
            "prompt_tokens": token_stats.get("prompt_tokens", 0),
            "completion_tokens": token_stats.get("completion_tokens", 0),
            "total_tokens": token_stats.get("total_tokens", 0),
            "eval_prompt_tokens": rel_token_stats.get("prompt_tokens", 0),
            "eval_completion_tokens": rel_token_stats.get("completion_tokens", 0),
            "eval_total_tokens": rel_token_stats.get("total_tokens", 0),
            "llm_cost": llm_cost,
        }
        return answer_data
    
    def _get_cost(self, tokens, input_cost=0, output_cost=0):
        cost = (
            tokens["prompt_tokens"] * input_cost + tokens["completion_tokens"] * output_cost
        ) / 1000
        return cost


    


