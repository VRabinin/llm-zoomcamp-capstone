import yaml, re, os

class Util:
    @staticmethod
    def __path_constructor(loader, node):
        """ Extract the matched value, expand env variable, and replace the match """
        path_matcher = re.compile(r'\$\{([^}^{]+)\}')          
        value = node.value
        match = path_matcher.match(value)
        env_var = match.group()[2:-1]
        return os.environ.get(env_var) + value[match.end():]        
        
    @staticmethod
    def load_yaml_config(yaml_file_path):
        path_matcher = re.compile(r'\$\{([^}^{]+)\}')        
        yaml.add_implicit_resolver('!path', path_matcher)
        yaml.add_constructor('!path', Util.__path_constructor)
        with open(yaml_file_path, 'r') as file:

            return yaml.load(file, Loader=yaml.FullLoader) 