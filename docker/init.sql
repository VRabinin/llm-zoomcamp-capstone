DROP TABLE IF EXISTS "feedback";
DROP TABLE IF EXISTS "conversations";
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    database_name TEXT NOT NULL,    
    model TEXT NOT NULL,
    search_provider TEXT NOT NULL,
    rag_parameters TEXT NOT NULL,
    response_time FLOAT NOT NULL,
    relevance TEXT NOT NULL,
    relevance_explanation TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    eval_prompt_tokens INTEGER NOT NULL,
    eval_completion_tokens INTEGER NOT NULL,
    eval_total_tokens INTEGER NOT NULL,
    llm_cost FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    feedback INTEGER NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE TABLE files (file_name text, file_data bytea);