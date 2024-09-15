from openai import OpenAI
import os
from index_util import Index


class LLM:
    def __init__(self, provider, model, **kwargs):
        self.provider = provider
        self.model = model
        self.prompt_factory = PromptFactory()
        if self.provider == "openai":
            api_key = kwargs.get("api_key")
            self.__init_openAI(api_key)
        
    def __init_openAI(self, api_key):
        self.llm = OpenAI(api_key=api_key)
        
    def prompt(self, prompt):
        if self.provider == "openai":
            return self.__query_openAI(prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
        
    def rag_query(self, query, schema, idx: Index, **kwargs):
        top_k = kwargs.get("top_k", 2)
        idx_results = idx.search(query, top_k, **kwargs)
        
        prompt = self.prompt_factory.get_prompt("basic_prompt", instruction=query, schema=schema)
        result = self.prompt(prompt)
        return result  
    
    def __query_openAI(self, prompt):
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.choices[0].message.content

    
class PromptFactory:
    def __init__(self):
        self.templates = {}
        templates_folder = "templates"
        for file_name in os.listdir(templates_folder):
            if file_name.endswith(".txt"):
                template_name = os.path.splitext(file_name)[0]
                file_path = f"templates/{file_name}"
                with open(file_path, 'r') as file:
                    self.templates[template_name] = file.read()
        
    def get_prompt(self, template_name, **kwargs):
        prompt_template = self.templates.get(template_name)
        return prompt_template.format(**kwargs)

