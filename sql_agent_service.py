import os
import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Union, Optional
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain.agents.agent_types import AgentType
from sqlalchemy import create_engine
from schemas import ChartDataPoint, TimeSeriesDataPoint, TableData, QueryResponse
from sqlalchemy.sql import text

load_dotenv()

class SQLAgentService:
    def __init__(self, database_url=None):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            self.database_url = self._build_database_url()
        
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            temperature=0
        )
        
        self.db = None
        self.agent_executor = None
        self.table_name = "commercial"  
        self._setup_database_connection()
        self._create_agent()
    
    def _build_database_url(self):
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME')
        username = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        
        if not all([database, username, password]):
            raise ValueError("Database credentials not found in environment variables")
        
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    def _setup_database_connection(self):
        try:
            engine = create_engine(self.database_url)
            self.db = SQLDatabase(engine, include_tables=['commercial'])
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {str(e)}")
    
    def _create_agent(self):
        commercial_schema = self.get_table_schema(self.table_name)
        
        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        
        system_message = f"""You are a SQL expert specialized in analyzing commercial licensing data. 

IMPORTANT RESTRICTIONS:
- You can ONLY query the 'commercial' table
- You cannot access any other tables in the database
- All queries must be SELECT statements on the commercial table only

COMMERCIAL TABLE SCHEMA:
{commercial_schema}

When asked questions about data, you should:
1. Generate the appropriate SQL query for the 'commercial' table ONLY
2. Execute it against the database
3. Always include the actual SQL query in your response using the format: ```sql\n[SQL_QUERY]\n```
4. Provide meaningful insights from the commercial data

Focus on commercial licensing insights such as:
- License distribution and patterns
- Business type analysis
- Geographic insights
- Timeline analysis
- Status and category breakdowns

Always format your response to include the SQL query even if you execute it successfully."""
        
        self.agent_executor = create_sql_agent(
            llm=self.llm,
            toolkit=toolkit,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            agent_executor_kwargs={
                "system_message": system_message
            }
        )
    
    def _detect_chart_type(self, df: pd.DataFrame, question: str) -> str:
        question_lower = question.lower()
        
        trend_keywords = ['trend', 'over time', 'timeline', 'monthly', 'daily', 'yearly', 'اتجاه', 'مع الوقت', 'شهريا', 'سنويا', 'تطور']
        percentage_keywords = ['percentage', 'proportion', 'share', 'distribution', 'نسبة', 'توزيع', 'حصة']
        comparison_keywords = ['compare', 'comparison', 'top', 'highest', 'lowest', 'مقارنة', 'أعلى', 'أقل', 'الأكثر', 'الأقل']
        
        if any(word in question_lower for word in trend_keywords):
            return "line"
        elif any(word in question_lower for word in percentage_keywords) and len(df) <= 10:
            return "pie"
        elif any(word in question_lower for word in comparison_keywords):
            return "bar"
        elif len(df) > 20:
            return "table"
        else:
            return "bar"
    
    def _format_for_chart(self, df: pd.DataFrame, chart_type: str) -> Union[List[ChartDataPoint], List[TimeSeriesDataPoint], TableData]:
        if chart_type == "table":
            return TableData(
                columns=df.columns.tolist(),
                rows=df.values.tolist()
            )
        
        if len(df.columns) < 2:
            raise ValueError("Data must have at least 2 columns for chart visualization")
        
        if chart_type == "line" and any(col.lower() in ['date', 'time', 'timestamp', 'created_at', 'updated_at'] for col in df.columns):
            time_col = None
            value_col = None
            
            for col in df.columns:
                if col.lower() in ['date', 'time', 'timestamp', 'created_at', 'updated_at']:
                    time_col = col
                elif df[col].dtype in ['int64', 'float64']:
                    value_col = col
            
            if time_col and value_col:
                result = []
                for _, row in df.iterrows():
                    timestamp = pd.to_datetime(row[time_col])
                    result.append(TimeSeriesDataPoint(
                        timestamp=timestamp,
                        value=float(row[value_col]),
                        metric=value_col
                    ))
                return result
        
        label_col = df.columns[0]
        value_col = None
        
        for col in df.columns[1:]:
            if df[col].dtype in ['int64', 'float64']:
                value_col = col
                break
        
        if not value_col:
            value_col = df.columns[1]
        
        result = []
        for _, row in df.iterrows():
            try:
                value = float(row[value_col]) if pd.notna(row[value_col]) else 0
            except (ValueError, TypeError):
                value = 0
            
            result.append(ChartDataPoint(
                label=str(row[label_col]),
                value=value,
                category=str(row[label_col])
            ))
        
        return result
    
    def _extract_sql_from_result(self, result: str) -> Optional[str]:
        sql_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*(SELECT.*?)\s*```',
            r'(SELECT\s+.*?)(?:\n(?!\s)|$)',
            r'(INSERT\s+.*?)(?:\n(?!\s)|$)',
            r'(UPDATE\s+.*?)(?:\n(?!\s)|$)',
            r'(DELETE\s+.*?)(?:\n(?!\s)|$)',
            r'Query:\s*(SELECT.*?)(?:\n|$)',
            r'SQL:\s*(SELECT.*?)(?:\n|$)',
        ]
        
        for pattern in sql_patterns:
            match = re.search(pattern, result, re.DOTALL | re.IGNORECASE)
            if match:
                sql = match.group(1).strip()
                sql = re.sub(r'\s+', ' ', sql)
                if sql.upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE')):
                    return sql
        
        lines = result.split('\n')
        for line in lines:
            line = line.strip()
            if line.upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE')):
                return line
        
        return None
    
    async def query(self, question: str, chart_type: str = "auto") -> QueryResponse:
        try:
            schema_info = self.get_table_schema(self.table_name)
            
            prompt = f"""You are a SQL expert analyzing commercial licensing data. Given the database schema and a question, generate ONLY the SQL query.

Database Schema for 'commercial' table:
{schema_info}

COLUMN UNDERSTANDING:
- g_issue_date: Issue dates (PRIMARY date column for issue analysis)
- g_expiration_date: Expiration dates (PRIMARY date column for expiration analysis)  
- issue_date, expiration_date: Secondary date columns (usually avoid these, prefer g_* versions)
- region_nmae: Region names
- isic_desc: Business type descriptions  
- lic_status: License status (analyze the actual values to understand active/inactive)
- baladia_name, amana_name, city_name: Geographic hierarchy
- shop_area: Numeric area measurements
- original_id: Original system ID

INTELLIGENT ANALYSIS APPROACH:
- When asked about "active vs expired/inactive", analyze based on:
  1. Current lic_status values AND/OR
  2. Compare g_expiration_date with CURRENT_DATE
  3. Use the data to determine what constitutes "active" vs "expired"
- For status analysis, examine actual lic_status values in the data
- For geographic analysis, choose appropriate level (region/city/baladia)
- For business analysis, use isic_desc for business types
- For temporal analysis, use g_issue_date as primary time dimension

ARABIC/MULTILINGUAL SUPPORT:
- Understand questions in Arabic and English
- Map Arabic business concepts to appropriate columns:
  - تاريخ/dates → g_issue_date, g_expiration_date
  - منطقة/region → region_nmae  
  - نشاط/business → isic_desc
  - حالة/status → lic_status
  - مدينة/city → city_name, baladia_name
  - فعال/active → determine from lic_status and/or dates
  - منتهي/expired → determine from lic_status and/or dates

SMART QUERY CONSTRUCTION:
1. Always return at least 2 columns for visualization
2. Use meaningful column aliases (e.g., 'license_count', 'status_type')
3. For status breakdowns, use CASE statements with descriptive labels
4. For counts, include category labels not just numbers
5. Group and order results logically
6. Use appropriate date functions for time analysis

Question: {question}

CONSTRAINTS:
- Query 'commercial' table ONLY
- Generate SELECT statements only
- Use column names exactly as they appear in schema
- Prefer g_issue_date and g_expiration_date for date operations
- Return results suitable for chart visualization (2+ columns)

Generate the SQL query that best answers this question:"""

            sql_response = self.llm.invoke(prompt)
            sql_query = sql_response.content.strip()
            
            # Clean up the response
            sql_query = re.sub(r'^```sql\s*', '', sql_query)
            sql_query = re.sub(r'\s*```$', '', sql_query)
            sql_query = re.sub(r'^```\s*', '', sql_query)
            sql_query = re.sub(r'\s*```$', '', sql_query)
            sql_query = sql_query.strip()
            
            # Security check: ensure query only contains SELECT and references commercial table
            if not sql_query.upper().startswith(('SELECT', 'WITH')):
                return QueryResponse(
                    success=False,
                    data=None,
                    chart_type="table",
                    insights=None,
                    message="Only SELECT queries are allowed",
                    error="Query must be a SELECT statement"
                )
            
            # Ensure query only references the commercial table
            if 'commercial' not in sql_query.lower():
                return QueryResponse(
                    success=False,
                    data=None,
                    chart_type="table",
                    insights=None,
                    message="Query must reference the commercial table",
                    error="Query does not reference the commercial table"
                )
            
            print(f"Debug - Generated SQL: {sql_query}")
            
            try:
                df = pd.read_sql(sql_query, self.db._engine)
                print(f"Debug - Query returned {len(df)} rows")
                
                if df.empty:
                    return QueryResponse(
                        success=True,
                        data=None,
                        chart_type="table",
                        insights="No data found matching the query criteria. This could indicate that the specified conditions don't match any records in the database.",
                        message="Query executed successfully but returned no data",
                        error=None
                    )
                
                if chart_type == "auto":
                    detected_chart_type = self._detect_chart_type(df, question)
                else:
                    detected_chart_type = chart_type
                
                chart_data = self._format_for_chart(df, detected_chart_type)
                
                # Generate insights about the data and chart
                insights = self._generate_insights(df, detected_chart_type, question)
                
                return QueryResponse(
                    success=True,
                    data=chart_data,
                    chart_type=detected_chart_type,
                    insights=insights,
                    message="Query executed successfully",
                    error=None
                )
                
            except Exception as data_error:
                print(f"Debug - Data processing error: {str(data_error)}")
                return QueryResponse(
                    success=False,
                    data=None,
                    chart_type="table",
                    insights=None,
                    message="Failed to process query results",
                    error=str(data_error)
                )
                
        except Exception as e:
            print(f"Debug - LLM error: {str(e)}")
            return QueryResponse(
                success=False,
                data=None,
                chart_type="table",
                insights=None,
                message="Failed to generate SQL query",
                error=str(e)
            )
    
    def _generate_insights(self, df: pd.DataFrame, chart_type: str, question: str) -> str:
        """Generate AI insights about the data and chart"""
        try:
            # Prepare data summary for insights
            data_summary = f"Data contains {len(df)} records with {len(df.columns)} columns. "
            
            # Add statistical insights
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            if len(numeric_cols) > 0:
                for col in numeric_cols:
                    total = df[col].sum()
                    avg = df[col].mean()
                    max_val = df[col].max()
                    min_val = df[col].min()
                    data_summary += f"{col}: Total={total:,.0f}, Average={avg:,.1f}, Max={max_val:,.0f}, Min={min_val:,.0f}. "
            
            # Add top categories if available
            text_cols = df.select_dtypes(include=['object']).columns
            if len(text_cols) > 0 and len(numeric_cols) > 0:
                for text_col in text_cols[:1]:  # Just first text column
                    if len(df) > 1:
                        top_category = df.loc[df[numeric_cols[0]].idxmax(), text_col]
                        top_value = df[numeric_cols[0]].max()
                        data_summary += f"Highest value: {top_category} with {top_value:,.0f}. "
            
            insights_prompt = f"""Based on the commercial licensing data analysis, provide concise and meaningful insights about the results:

Question Asked: {question}
Chart Type: {chart_type}
Data Summary: {data_summary}

Sample Data (first 3 rows):
{df.head(3).to_string()}

Provide insights that include:
1. Key findings from the data
2. Notable patterns or trends
3. Business implications
4. Chart interpretation guidance

Keep the response concise (2-3 sentences) and focus on actionable insights. Use both Arabic and English terms when appropriate."""

            insights_response = self.llm.invoke(insights_prompt)
            return insights_response.content.strip()
            
        except Exception as e:
            return f"Data shows {len(df)} records. Chart type '{chart_type}' is suitable for visualizing this data distribution."
    
    def get_table_schema(self, table_name: str) -> str:
        """Get detailed schema information for a specific table"""
        try:
            return self.db.get_table_info_no_throw([table_name])
        except:
            try:
                with self.db._engine.connect() as conn:
                    result = conn.execute(text(f"""
                        SELECT 
                            column_name,
                            data_type,
                            is_nullable,
                            column_default
                        FROM information_schema.columns 
                        WHERE table_name = '{table_name}' 
                        ORDER BY ordinal_position
                    """))
                    columns = result.fetchall()
                    
                    schema_info = f"Table: {table_name}\nColumns:\n"
                    for col_name, data_type, is_nullable, default in columns:
                        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                        default_info = f" DEFAULT {default}" if default else ""
                        schema_info += f"  - {col_name}: {data_type} {nullable}{default_info}\n"
                    
                    return schema_info
            except Exception as e:
                return f"Table: {table_name}\nError getting schema: {str(e)}"
    
    def get_database_info(self) -> Dict[str, Any]:
        tables = self.db.get_usable_table_names()
        table_schemas = {}
        
        for table in tables:
            try:
                schema_info = self.db.get_table_info_no_throw([table])
                table_schemas[table] = schema_info
            except Exception:
                table_schemas[table] = "Schema information not available"
        
        return {
            "tables": tables,
            "table_schemas": table_schemas
        } 