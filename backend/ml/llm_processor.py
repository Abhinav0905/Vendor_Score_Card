from langchain.llms import OpenAI
from langchain.chains import create_sql_query_chain
from langchain.prompts import PromptTemplate
from typing import Dict, Any
import os

class LLMQueryProcessor:
    def __init__(self):
        self.llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.db_schema = """
        CREATE TABLE suppliers (
            id UUID PRIMARY KEY,
            name TEXT,
            data_accuracy FLOAT,
            error_rate FLOAT,
            compliance_score FLOAT,
            response_time INTEGER,
            last_submission TIMESTAMP
        );
        """
        
    def process_query(self, natural_query: str) -> Dict[str, Any]:
        prompt = PromptTemplate(
            template="""Given the following SQL Schema:
            {schema}
            
            Convert this natural language query into SQL:
            {query}
            
            The SQL query should be:""",
            input_variables=["schema", "query"]
        )
        
        chain = create_sql_query_chain(self.llm, prompt)
        sql_query = chain.run(schema=self.db_schema, query=natural_query)
        
        return {
            "sql": sql_query,
            "natural_query": natural_query
        }