#!/bin/bash
# Set the working directory to sql_generator
cd sql_generator
# Run the Streamlit application
POSTGRES_HOST=localhost POSTGRES_PORT=$POSTGRES_L_PORT streamlit run app.py --server.port=8501 --server.address=127.0.0.1