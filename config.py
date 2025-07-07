import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME')
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
    
    # Oracle Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL')  # Full Oracle connection string if provided
    
    # Oracle specific settings (fallback if DATABASE_URL not provided)
    DB_USER = os.getenv('DB_USER', 'AI_READ')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'Ai2025aI')
    DB_TNS = os.getenv('DB_TNS')  # Optional custom TNS string
    
    # Oracle Materialized Views
    ORACLE_MATERIALIZED_VIEWS = [
        "AI_USER.COMMERCIAL_LICENSE_MV",
        "AI_USER.COM_LIC_ADDITIONAL_ACTIVITY_MV", 
        "AI_USER.COM_REQUESTS_COMPLETE_MV"
    ]
    
    # LLM Configuration
    LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-3.5-turbo')
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0'))
    
    @classmethod
    def validate(cls):
        # Check Azure OpenAI requirements
        azure_required_vars = ['AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_DEPLOYMENT_NAME']
        missing_azure_vars = [var for var in azure_required_vars if not getattr(cls, var)]
        
        if missing_azure_vars:
            raise ValueError(f"Missing required Azure OpenAI environment variables: {', '.join(missing_azure_vars)}")
        
        # Check Oracle database requirements
        if not cls.DATABASE_URL:
            # If no full connection string, check for basic Oracle credentials
            oracle_vars = ['DB_USER', 'DB_PASSWORD']
            missing_oracle_vars = [var for var in oracle_vars if not getattr(cls, var)]
            if missing_oracle_vars:
                raise ValueError(f"Missing Oracle database configuration: {', '.join(missing_oracle_vars)}")
        
        return True
    
    @classmethod
    def get_oracle_info(cls):
        """Get Oracle connection information for debugging"""
        return {
            'database_url': cls.DATABASE_URL[:50] + '...' if cls.DATABASE_URL and len(cls.DATABASE_URL) > 50 else cls.DATABASE_URL,
            'db_user': cls.DB_USER,
            'db_password': '***' if cls.DB_PASSWORD else None,
            'materialized_views': cls.ORACLE_MATERIALIZED_VIEWS
        } 