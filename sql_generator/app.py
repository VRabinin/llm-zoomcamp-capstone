import os, re, uuid
import streamlit as st
import pandas as pd
from db import DBConnection
from search import SearchFactory, SearchTypes
from llm import LLM, PromptGenerator
from time import time

#------------------------------------------------ Initialization ------------------------------------------------
def init_session_var(names: list[str], value=None):
    for name in names:
        if name not in st.session_state:
            st.session_state[name] = value

@st.cache_resource(show_spinner=False)
def init_application():   
    db_conn = DBConnection(\
            db_type='postgresql',
            db_name = os.environ['POSTGRES_DB'],
            db_host = os.environ['POSTGRES_HOST'],
            db_port = os.environ['POSTGRES_PORT'], 
            db_user = os.environ['POSTGRES_USER'] ,
            db_password = os.environ['POSTGRES_PASSWORD'],
            read_only=False
    )
    
    llm_model = LLM("config/llm.yaml")
    search_providers = {}
    search_providers['Fuzzywuzzy'] = SearchFactory.get_search_provider(SearchTypes.FUZZY_SEARCH, db_conn=db_conn)
    search_providers['Elasticsearch'] = SearchFactory.get_search_provider(SearchTypes.ELASTICSEARCH)
    prompt_generator = PromptGenerator("templates/")
    
    return db_conn, llm_model, search_providers, prompt_generator

@st.cache_data(show_spinner=False)
def get_db_metadata(_db_conn: DBConnection):
    db_list = _db_conn.get_database_list()
    return db_list


db_conn, llm_model, search_providers, prompt_generator = init_application()
#db_list = db_conn.get_database_list()
db_list = get_db_metadata(db_conn)
llm_list = llm_model.get_model_list()




#------------------------------------------------ Session State ------------------------------------------------
init_session_var(['sql_statement',
                  'sql_results',
                  'db_tables',
                  'conversation_id',
                  'feedback',])

#------------------------------------------------ Business Logic ------------------------------------------------

# Function to generate SQL statement (Main function)
def generate_sql(user_question, db_selection, sp_selection, llm_selection, similarity_threshold, num_synonyms):
    start_time = time()
    db_conn.set_curr_database(db_selection)    
    st.session_state['conversation_id'] = None
    conversation_id = str(uuid.uuid4())     
    st.session_state['feedback'] = None
    discovered_tables = search_providers[sp_selection].search_by_query(db_name=db_selection,
                                                        query=user_question, 
                                                        similarity_threshold=similarity_threshold, 
                                                        max_synonyms=num_synonyms)
    if len(discovered_tables) == 0:
        end_time = time()    
        response_time = end_time - start_time 
        response_data = {
            "answer": "No tables found",
            "database_name": db_selection,
            "model": "N/A",
            "search_provider": sp_selection,
            "rag_parameters": str({"similarity_threshold": similarity_threshold, "max_synonyms": num_synonyms}),
            "relevance": "N/A",
            "relevance_explanation": "N/A",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "eval_prompt_tokens": 0,
            "eval_completion_tokens": 0,
            "eval_total_tokens": 0,
            "llm_cost": 0,
            "response_time": response_time
        }
        db_conn.save_conversation(conversation_id, user_question, response_data)    
        return "No tables found", None
    
    prompt = prompt_generator.get_prompt(template_name='basic_prompt', 
                                         schema=discovered_tables, 
                                         instruction=user_question)
    response_data = llm_model.prompt(llm_selection, prompt)
    response = response_data['answer']
    
    sql_pattern = r"<SQL>([\s\S]*?)(?=<\/SQL>)"
    try:
        sql_statement = str(re.search(sql_pattern, response).group(1)).strip()
    except:
        end_time = time()    
        response_time = end_time - start_time 
        response_data = {
            "answer": "No tables found",
            "database_name": db_selection,
            "model": "N/A",
            "search_provider": sp_selection,
            "rag_parameters": str({"similarity_threshold": similarity_threshold, "max_synonyms": num_synonyms}),
            "relevance": "N/A",
            "relevance_explanation": "N/A",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "eval_prompt_tokens": 0,
            "eval_completion_tokens": 0,
            "eval_total_tokens": 0,
            "llm_cost": 0,
            "response_time": response_time
        }
        db_conn.save_conversation(conversation_id, user_question, response_data)    
        return "Response: " + response, None
            
    end_time = time()    
    response_time = end_time - start_time
    st.session_state['conversation_id'] = conversation_id    
       
    response_data['response_time'] = response_time
    response_data["database_name"] = db_selection,
    response_data["search_provider"] = sp_selection,
    response_data["rag_parameters"] = str({"similarity_threshold": similarity_threshold, "max_synonyms": num_synonyms}),
    
    db_conn.save_conversation(conversation_id, user_question, response_data)
    
    return sql_statement, discovered_tables
    #return None, None

def register_feedback(conversation_id: str, feedback: int):
    if feedback not in [-1, 1]:
        return "Invalid feedback"
    db_conn.save_feedback(conversation_id, feedback)
    return f"Feedback {feedback} registered"

# Function to execute SQL statement
def execute_sql(sql_statement):
    return db_conn.execute_sql(sql_statement)


#------------------------------------------------ Event Processors ------------------------------------------------

def process_button_click():
    sql_statement, db_tables = generate_sql(user_question, 
                                            db_selection, 
                                            sp_selection,
                                            llm_selection, 
                                            sim_threshold, 
                                            num_synonyms)
    st.session_state['sql_statement'] = sql_statement
    st.session_state['db_tables'] = db_tables
    st.session_state['sql_results'] = None

def run_sql_button_click():
    st.session_state['sql_results'] = execute_sql(generated_sql)

def clear_results_button_click():
    st.session_state['sql_results'] = None
    
def reload_all():
    st.cache_data.clear()
    st.cache_resource.clear()
    
#------------------------------------------------ Streamlit UI ------------------------------------------------
st.set_page_config(layout="wide")

# Streamlit layout
st.title("SQL Code Generator")

left_col, mid_col, right_col = st.columns([1, 2, 3])
with left_col:
    col1, col2 = st.columns(2)
    with col1:
        reload_all_button = st.button("Reload All", on_click=reload_all)
    with col2:
        process_button = st.button("Process", on_click=process_button_click)    
    
with mid_col:
    if st.session_state['sql_statement']:       
        run_sql_button = st.button("Run SQL on DB", on_click=run_sql_button_click)        

# Elements in the right column
with right_col:
    if st.session_state['sql_results'] is not None:        
        clear_results_button = st.button("Clear Results", on_click=clear_results_button_click)

# Create three columns
left_col, mid_col, right_col = st.columns([1, 2, 3])

# Elements in the left column
with left_col:
    user_question = st.text_area("Enter your question:", "Top 5 movies by number of rentals")
    db_selection = st.selectbox("Select Database:", db_list)
    llm_selection = st.selectbox("Select LLM:", llm_list)
    st.markdown('----')
    sp_selection = st.selectbox("Select Search Provider:", search_providers.keys())
    sim_threshold = st.slider("Similarity Threshold:", 60, 100, 80)
    num_synonyms = st.number_input("Number of Synonyms:", 0, 20, 5)

# Elements in the mid column
with mid_col:
    if st.session_state['sql_statement']:        
        generated_sql = st.text_area("Generated SQL Statement:", st.session_state['sql_statement'], height=200)
        if st.session_state['conversation_id'] is not None:
            st.write("Was the generated SQL statement helpful?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("👍"):
                    register_feedback(st.session_state['conversation_id'], 1)
                    st.session_state['feedback'] = 1
            with col2:
                if st.button("👎"):
                    register_feedback(st.session_state['conversation_id'], -1)
                    st.session_state['feedback'] = -1
        if st.session_state['feedback'] is not None:
            st.write(f"Feedback: {st.session_state['feedback']}. Thank you!")

# Elements in the right column
with right_col:
    if st.session_state['sql_results'] is not None:        
        st.dataframe(st.session_state['sql_results'])    
            
#Bottom section with related tables 
if st.session_state['sql_statement']:                
    st.text("Related Tables")        
    st.text(st.session_state['db_tables'])