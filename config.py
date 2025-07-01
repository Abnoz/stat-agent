import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME')
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
    
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    
    LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-3.5-turbo')
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0'))
    
    @classmethod
    def validate(cls):
        required_vars = ['AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_DEPLOYMENT_NAME']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        
        if missing_vars:
            raise ValueError(f"Missing required Azure OpenAI environment variables: {', '.join(missing_vars)}")
        
        if not cls.DATABASE_URL:
            db_vars = ['DB_NAME', 'DB_USER', 'DB_PASSWORD']
            missing_db_vars = [var for var in db_vars if not getattr(cls, var)]
            if missing_db_vars:
                raise ValueError(f"Missing database configuration: {', '.join(missing_db_vars)}")
        
        return True 