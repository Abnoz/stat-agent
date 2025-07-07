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
import oracledb

load_dotenv()

class SQLAgentService:
    def __init__(self, database_url=None):
        # Oracle connection configuration - using direct connection like your test
        self.official_tns = """(DESCRIPTION=(ADDRESS_LIST=(FAILOVER=ON)(LOAD_BALANCE=ON)(ADDRESS=(PROTOCOL=TCP)(HOST=ruhmpp-exa-scan.momra.net)(PORT=1521))(ADDRESS=(PROTOCOL=TCP)(HOST=drmpp-exa-scan.momra.net)(PORT=1521)))(CONNECT_DATA=(SERVICE_NAME=MEDIUM_AIDBPRO.momra.net)(FAILOVER_MODE=(TYPE=select)(METHOD=basic))))"""
        self.db_user = os.getenv('DB_USER', 'AI_READ')
        self.db_password = os.getenv('DB_PASSWORD', 'Ai2025aI')
        
        # Materialized views available
        self.materialized_views = [
            "AI_USER.COMMERCIAL_LICENSE_MV",
            "AI_USER.COM_LIC_ADDITIONAL_ACTIVITY_MV", 
            "AI_USER.COM_REQUESTS_COMPLETE_MV"
        ]
        
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            temperature=0
        )
        
        self.db = None
        self.oracle_connection = None
        self.main_table = "AI_USER.COMMERCIAL_LICENSE_MV"  # Primary table for commercial data
        self._setup_oracle_connection()
        self._setup_database_connection()
        self._create_agent()
    
    def _setup_oracle_connection(self):
        """Setup direct Oracle connection for queries"""
        try:
            self.oracle_connection = oracledb.connect(
                user=self.db_user,
                password=self.db_password,
                dsn=self.official_tns
            )
            print("✅ Direct Oracle connection established successfully")
        except Exception as e:
            raise ConnectionError(f"Failed to establish direct Oracle connection: {str(e)}")
    
    def _build_oracle_url(self):
        """Create Oracle connection URL for SQLAlchemy"""
        return f"oracle+oracledb://{self.db_user}:{self.db_password}@{self.official_tns}"
    
    def _setup_database_connection(self):
        """Setup SQLAlchemy connection for LangChain agent"""
        try:
            database_url = self._build_oracle_url()
            engine = create_engine(database_url)
            # Include all materialized views in the database connection
            self.db = SQLDatabase(engine, include_tables=self.materialized_views)
            print("✅ SQLAlchemy Oracle connection established for LangChain")
        except Exception as e:
            print(f"⚠️ SQLAlchemy connection failed, will use direct Oracle connection: {str(e)}")
            # We can still proceed with direct Oracle connection for queries
    
    def _create_agent(self):
        # Get schema for primary commercial table
        commercial_schema = self.get_table_schema(self.main_table)
        
        # Get schemas for all available materialized views
        all_schemas = ""
        for mv in self.materialized_views:
            mv_schema = self.get_table_schema(mv)
            all_schemas += f"\n{mv_schema}\n"
        
        # Only create LangChain agent if SQLAlchemy connection is available
        if self.db is not None:
            try:
                toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
                
                system_message = f"""You are a SQL expert specialized in analyzing commercial licensing data from Oracle materialized views.

IMPORTANT RESTRICTIONS:
- You can ONLY query these materialized views: {', '.join(self.materialized_views)}
- You cannot access any other tables in the database
- All queries must be SELECT statements on these materialized views only
- Use Oracle SQL syntax

AVAILABLE MATERIALIZED VIEWS:
{all_schemas}

PRIMARY TABLE FOR MOST QUERIES: {self.main_table}
- This contains the main commercial licensing data
- Use this for most general commercial license questions

ADDITIONAL TABLES:
- AI_USER.COM_LIC_ADDITIONAL_ACTIVITY_MV: Additional activities data
- AI_USER.COM_REQUESTS_COMPLETE_MV: Complete request information

When asked questions about data, you should:
1. Generate the appropriate Oracle SQL query for the relevant materialized view(s)
2. Execute it against the database
3. Always include the actual SQL query in your response using the format: ```sql\n[SQL_QUERY]\n```
4. Provide meaningful insights from the commercial data

Focus on commercial licensing insights such as:
- License distribution and patterns
- Business type analysis
- Geographic insights
- Timeline analysis
- Status and category breakdowns

ORACLE SQL SPECIFIC NOTES:
- Use Oracle date functions (TO_DATE, TRUNC, etc.)
- Use Oracle-specific syntax for date operations
- Use ROWNUM for limiting results instead of LIMIT
- Use NVL for null handling

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
                print("✅ LangChain SQL Agent created successfully")
            except Exception as e:
                print(f"⚠️ LangChain agent creation failed, using direct Oracle queries only: {str(e)}")
                self.agent_executor = None
        else:
            print("⚠️ Using direct Oracle connection only (no LangChain agent)")
            self.agent_executor = None
    
    def _detect_chart_type(self, df: pd.DataFrame, question: str) -> str:
        question_lower = question.lower()
        
        # Single value responses - no chart needed
        if len(df.columns) == 1 and len(df) == 1:
            count_keywords = ['count', 'total', 'number', 'how many', 'عدد', 'إجمالي', 'كم', 'مجموع']
            if any(word in question_lower for word in count_keywords):
                return "none"  # No chart needed for single values
        
        # Single column with single row - usually a summary statistic
        if len(df.columns) == 1 and len(df) == 1:
            return "none"
        
        # Single column with multiple rows - could be a list, but check context
        if len(df.columns) == 1:
            # If it's just a list of values without clear categories, might not need a chart
            if len(df) > 50:  # Too many items for effective visualization
                return "table"
            return "bar"  # Simple bar chart for single column with multiple values
        
        # Two columns where one is clearly a count/total - good for charts
        if len(df.columns) == 2:
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            text_cols = df.select_dtypes(include=['object']).columns
            
            # Perfect for charts: category + numeric value
            if len(numeric_cols) == 1 and len(text_cols) == 1:
                # Check for different chart types based on context
                trend_keywords = ['trend', 'over time', 'timeline', 'monthly', 'daily', 'yearly', 'اتجاه', 'مع الوقت', 'شهريا', 'سنويا', 'تطور']
                percentage_keywords = ['percentage', 'proportion', 'share', 'distribution', 'نسبة', 'توزيع', 'حصة']
                comparison_keywords = ['compare', 'comparison', 'top', 'highest', 'lowest', 'مقارنة', 'أعلى', 'أقل', 'الأكثر', 'الأقل']
                
                if any(word in question_lower for word in trend_keywords):
                    return "line"
                elif any(word in question_lower for word in percentage_keywords) and len(df) <= 10:
                    return "pie"
                elif any(word in question_lower for word in comparison_keywords):
                    return "bar"
                elif len(df) <= 10:  # Small number of categories - good for pie
                    return "pie"
                else:
                    return "bar"  # Default for category + value
        
        # Multiple columns - usually better as table unless specifically requested
        if len(df.columns) > 2:
            chart_keywords = ['chart', 'graph', 'visualize', 'plot', 'رسم', 'مخطط', 'رسم بياني']
            if any(word in question_lower for word in chart_keywords):
                return "bar"  # User explicitly wants a chart
            elif len(df) > 20:  # Too much data for effective charting
                return "table"
            else:
                return "table"  # Default to table for complex data
        
        # Large datasets - prefer table
        if len(df) > 50:
            return "table"
        
        # Default fallback
        return "bar"
    
    def _format_for_chart(self, df: pd.DataFrame, chart_type: str) -> Union[List[ChartDataPoint], List[TimeSeriesDataPoint], TableData]:
        # Handle when no chart is needed
        if chart_type == "none":
            return TableData(
                columns=df.columns.tolist(),
                rows=df.values.tolist()
            )
        
        # Handle insight type for single values (legacy support)
        if chart_type == "insight":
            return TableData(
                columns=df.columns.tolist(),
                rows=df.values.tolist()
            )
        
        if chart_type == "table":
            return TableData(
                columns=df.columns.tolist(),
                rows=df.values.tolist()
            )
        
        if len(df.columns) < 2:
            # If we have less than 2 columns but chart_type is not insight, convert to table
            return TableData(
                columns=df.columns.tolist(),
                rows=df.values.tolist()
            )
        
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
            import re  # Move import to top of method
            
            schema_info = self.get_table_schema(self.main_table)
            
            # Extract just the column names from schema for clearer reference
            column_names = []
            if "Columns:" in schema_info:
                lines = schema_info.split('\n')
                for line in lines:
                    if line.strip().startswith('- '):
                        col_name = line.split(':')[0].replace('- ', '').strip()
                        column_names.append(col_name)
            
            columns_list = ', '.join(column_names) if column_names else "Unable to extract columns"
            
            print(f"Debug - Extracted column names: {column_names}")
            print(f"Debug - Columns list: {columns_list}")
            
            # If no columns extracted, force a simple count query
            if not column_names:
                print("Debug - No columns extracted, forcing simple count query")
                sql_query = f"SELECT COUNT(*) as total_count FROM {self.main_table}"
                print(f"Debug - Using safe fallback query: {sql_query}")
                
                try:
                    # Execute the safe query directly
                    cursor = self.oracle_connection.cursor()
                    print(f"Debug - About to execute fallback query: {sql_query}")
                    
                    cursor.execute(sql_query)
                    print(f"Debug - Fallback query executed successfully!")
                    
                    # Fetch results and convert to DataFrame
                    columns = [desc[0] for desc in cursor.description]
                    print(f"Debug - Result columns: {columns}")
                    
                    rows = cursor.fetchall()
                    print(f"Debug - Fetched {len(rows)} rows")
                    
                    cursor.close()
                    
                    df = pd.DataFrame(rows, columns=columns)
                    print(f"Debug - DataFrame created with {len(df)} rows and columns: {df.columns.tolist()}")
                    
                    if chart_type == "auto":
                        detected_chart_type = self._detect_chart_type(df, question)
                    else:
                        detected_chart_type = chart_type
                    
                    chart_data = self._format_for_chart(df, detected_chart_type)
                    insights = self._generate_insights(df, detected_chart_type, question)
                    
                    return QueryResponse(
                        success=True,
                        data=chart_data,
                        chart_type=detected_chart_type,
                        insights=insights,
                        message="Query executed successfully using fallback",
                        error=None
                    )
                    
                except Exception as fallback_error:
                    print(f"Debug - Even fallback query failed: {fallback_error}")
                    return QueryResponse(
                        success=False,
                        data=None,
                        chart_type="table",
                        insights=None,
                        message="Failed to execute even simple count query",
                        error=str(fallback_error)
                    )
            
            print(f"Debug - Full schema info:")
            print(schema_info)
            print("=" * 50)
            
            prompt = f"""CRITICAL: Generate ONLY a clean Oracle SQL SELECT statement. No explanations, no markdown, no extra text.

TABLE: {self.main_table}

AVAILABLE COLUMNS (use EXACTLY these names):
{columns_list}

FULL SCHEMA:
{schema_info}

QUESTION: {question}

COLUMN MAPPING FOR ARABIC TERMS:
- أمانة/أمانات/Amana/Amanat → AMANA_NAME
- بلدية/باليديا/Municipality → BALADIA_NAME  
- منطقة/Region → REGION_NMAE
- مدينة/City → CITY_NAME
- نشاط/Activity → D_ACTIVITIES_NAME
- حالة/Status → LIC_STATUS
- رخصة/License → LICENSE_ID (for counting)

STRICT RULES - VIOLATE ANY RULE AND SYSTEM FAILS:
1. START WITH "SELECT" - NOTHING ELSE
2. USE ONLY THESE COLUMN NAMES: {columns_list}
3. USE EXACT TABLE NAME: {self.main_table}
4. NO SEMICOLONS AT END
5. NO MARKDOWN, NO BACKTICKS, NO EXPLANATIONS
6. ONLY ASCII CHARACTERS

COMMON PATTERNS FOR YOUR QUESTION:
- License distribution by Amana: SELECT AMANA_NAME, COUNT(*) as license_count FROM {self.main_table} GROUP BY AMANA_NAME ORDER BY license_count DESC
- License distribution by Region: SELECT REGION_NMAE, COUNT(*) as license_count FROM {self.main_table} GROUP BY REGION_NMAE ORDER BY license_count DESC
- License distribution by Activity: SELECT D_ACTIVITIES_NAME, COUNT(*) as license_count FROM {self.main_table} GROUP BY D_ACTIVITIES_NAME ORDER BY license_count DESC

OUTPUT ONLY THE SQL - NO OTHER TEXT:"""

            sql_response = self.llm.invoke(prompt)
            raw_sql = sql_response.content.strip()
            print(f"Debug - Raw LLM response: '{raw_sql}'")
            
            # Clean up the response more thoroughly
            sql_query = re.sub(r'^```sql\s*', '', raw_sql, flags=re.IGNORECASE)
            sql_query = re.sub(r'\s*```$', '', sql_query)
            sql_query = re.sub(r'^```\s*', '', sql_query)
            sql_query = re.sub(r'\s*```$', '', sql_query)
            sql_query = re.sub(r'^SQL Query:\s*', '', sql_query, flags=re.IGNORECASE)
            sql_query = re.sub(r'^Query:\s*', '', sql_query, flags=re.IGNORECASE)
            
            # Remove trailing semicolons that cause ORA-00933
            sql_query = re.sub(r';\s*$', '', sql_query)
            
            # PRESERVE QUOTED STRINGS (including Arabic text) before cleaning
            quoted_strings = []
            def preserve_quotes(match):
                quoted_strings.append(match.group(0))
                return f"__QUOTED_STRING_{len(quoted_strings)-1}__"
            
            # Preserve both single and double quoted strings
            sql_query = re.sub(r"'([^']*)'", preserve_quotes, sql_query)
            sql_query = re.sub(r'"([^"]*)"', preserve_quotes, sql_query)
            
            # Now clean problematic characters ONLY outside of quotes
            sql_query = sql_query.replace('"', '"').replace('"', '"')
            sql_query = sql_query.replace(''', "'").replace(''', "'")
            sql_query = sql_query.replace('–', '-').replace('—', '-')
            sql_query = sql_query.replace('…', '...')
            
            # Remove any non-ASCII characters except in preserved quoted strings
            # Keep basic SQL characters and placeholder tokens
            cleaned_chars = []
            for char in sql_query:
                if (ord(char) < 128 or char.isspace() or 
                    sql_query[max(0, sql_query.find(char)-10):sql_query.find(char)+10].find('__QUOTED_STRING_') != -1):
                    cleaned_chars.append(char)
                else:
                    cleaned_chars.append(' ')
            sql_query = ''.join(cleaned_chars)
            
            # Restore quoted strings with their original content (including Arabic)
            for i, quoted_string in enumerate(quoted_strings):
                sql_query = sql_query.replace(f"__QUOTED_STRING_{i}__", quoted_string)
            
            # Remove any extra whitespace
            sql_query = ' '.join(sql_query.split())
            sql_query = sql_query.strip()
            
            # Ensure only valid SQL characters remain (letters, numbers, spaces, common SQL punctuation)
            sql_query = re.sub(r'[^\w\s\(\)\.,=<>!\-\+\*\/\'\"_]', ' ', sql_query)
            sql_query = ' '.join(sql_query.split())  # Clean up extra spaces
            
            print(f"Debug - Cleaned SQL query: '{sql_query}'")
            
            # If the query doesn't start with SELECT, try to fix it
            if not sql_query.upper().startswith(('SELECT', 'WITH')):
                # Try to extract SELECT from the response
                select_match = re.search(r'(SELECT\s+.*)', sql_query, re.IGNORECASE | re.DOTALL)
                if select_match:
                    sql_query = select_match.group(1).strip()
                    print(f"Debug - Extracted SELECT query: '{sql_query}'")
                else:
                    # Generate a safe fallback query based on question content
                    question_lower = question.lower()
                    if any(word in question_lower for word in ['total', 'count', 'number', 'how many', 'عدد', 'إجمالي', 'كم']):
                        sql_query = f"SELECT COUNT(*) as total_count FROM {self.main_table}"
                    else:
                        # Default to simple count
                        sql_query = f"SELECT COUNT(*) as total_count FROM {self.main_table}"
                    print(f"Debug - Using fallback query: '{sql_query}'")
            
            # Additional validation: ensure the query is reasonable
            if len(sql_query.strip()) < 10:  # Too short to be valid
                sql_query = f"SELECT COUNT(*) as total_count FROM {self.main_table}"
                print(f"Debug - Query too short, using fallback: '{sql_query}'")
            
            # Check for obvious issues and fix them
            if 'FROM ' not in sql_query.upper():
                sql_query = f"SELECT COUNT(*) as total_count FROM {self.main_table}"
                print(f"Debug - No FROM clause, using fallback: '{sql_query}'")
            
            # Validate that only actual columns from the schema are used
            if column_names:
                query_upper = sql_query.upper()
                # Split query into tokens more intelligently
                # Use regex to properly tokenize SQL, preserving function calls
                tokens = re.findall(r'\b\w+\b', sql_query)
                
                print(f"Debug - SQL tokens to validate: {tokens}")
                
                # Check for invalid column references
                for token in tokens:
                    # Skip SQL keywords, functions, operators, and table names
                    sql_keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 
                                  'AS', 'AND', 'OR', 'DESC', 'ASC', 'HAVING', 'DISTINCT', 'TOP', 'LIMIT', 'ROWNUM',
                                  'AI_USER', 'COMMERCIAL_LICENSE_MV']
                    
                    # Oracle-specific functions and keywords
                    oracle_functions = ['TO_CHAR', 'TO_DATE', 'TO_NUMBER', 'NVL', 'NVL2', 'DECODE', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
                                       'SUBSTR', 'LENGTH', 'UPPER', 'LOWER', 'TRIM', 'LTRIM', 'RTRIM', 'ROUND', 'TRUNC', 'CEIL', 'FLOOR',
                                       'EXTRACT', 'SYSDATE', 'SYSTIMESTAMP', 'ADD_MONTHS', 'MONTHS_BETWEEN']
                    
                    # Date format patterns
                    date_formats = ['YYYY', 'MM', 'DD', 'HH24', 'MI', 'SS', 'MON', 'MONTH', 'DY', 'DAY']
                    
                    if (token.upper() in sql_keywords or 
                        token.upper() in oracle_functions or
                        token.upper() in date_formats or
                        token in column_names or
                        token.isdigit() or 
                        len(token) <= 2 or
                        token.startswith('license_') or  # Allow aliases like license_count
                        token.startswith('total_') or   # Allow aliases like total_count
                        token.startswith('issue_') or   # Allow aliases like issue_month
                        token.endswith('_count') or    # Allow any count aliases
                        token.endswith('_sum') or      # Allow sum aliases
                        token.endswith('_avg') or      # Allow avg aliases
                        token.endswith('_month') or    # Allow month aliases
                        token.endswith('_year') or     # Allow year aliases
                        token.endswith('_date')):      # Allow date aliases
                        continue
                    
                    # If we get here, it might be an invalid column - but be less strict
                    print(f"Debug - Checking potentially invalid token: '{token}'")
                    if token not in column_names:
                        print(f"Debug - Token '{token}' not in columns, but allowing Oracle to validate...")
                        # Don't immediately fallback - let Oracle handle the validation
                        # Only fallback for obviously wrong things
                        continue
            
            print(f"Debug - FINAL SQL TO EXECUTE: '{sql_query}'")
            
            # Validate the query starts with SELECT
            if not sql_query.upper().startswith(('SELECT', 'WITH')):
                return QueryResponse(
                    success=False,
                    data=None,
                    chart_type="table",
                    insights=None,
                    message="Only SELECT queries are allowed",
                    error=f"Query must be a SELECT statement. Generated: '{sql_query}'"
                )
            
            # Ensure query only references allowed materialized views
            query_lower = sql_query.lower()
            mv_referenced = any(mv.lower() in query_lower for mv in self.materialized_views)
            if not mv_referenced:
                return QueryResponse(
                    success=False,
                    data=None,
                    chart_type="table",
                    insights=None,
                    message="Query must reference one of the allowed materialized views",
                    error=f"Query does not reference any of: {', '.join(self.materialized_views)}"
                )
            
            print(f"Debug - Final Oracle SQL: {sql_query}")
            
            try:
                # Use direct Oracle connection for query execution
                cursor = self.oracle_connection.cursor()
                print(f"Debug - About to execute query: {sql_query}")
                
                cursor.execute(sql_query)
                print(f"Debug - Query executed successfully!")
                
                # Fetch results and convert to DataFrame
                columns = [desc[0] for desc in cursor.description]
                print(f"Debug - Result columns: {columns}")
                
                rows = cursor.fetchall()
                print(f"Debug - Fetched {len(rows)} rows")
                
                cursor.close()
                
                df = pd.DataFrame(rows, columns=columns)
                print(f"Debug - DataFrame created with {len(df)} rows and columns: {df.columns.tolist()}")
                
                if df.empty:
                    return QueryResponse(
                        success=True,
                        data=None,
                        chart_type="table",
                        insights="No data available for this question. The query executed successfully but found no records matching the specified criteria in the database.",
                        message="No data available for this question",
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
                print(f"Debug - Oracle execution error details:")
                print(f"  - Error type: {type(data_error).__name__}")
                print(f"  - Error message: {str(data_error)}")
                print(f"  - Query that failed: {sql_query}")
                return QueryResponse(
                    success=False,
                    data=None,
                    chart_type="table",
                    insights=None,
                    message="Failed to process Oracle query results",
                    error=f"SQL: {sql_query} | Error: {str(data_error)}"
                )
                
        except Exception as e:
            print(f"Debug - LLM error: {str(e)}")
            return QueryResponse(
                success=False,
                data=None,
                chart_type="table",
                insights=None,
                message="Failed to generate Oracle SQL query",
                error=str(e)
            )
    
    def _generate_insights(self, df: pd.DataFrame, chart_type: str, question: str) -> str:
        """Generate AI insights about the data and chart"""
        try:
            # Handle empty data case
            if df.empty:
                return "No data available for this question. The query executed successfully but found no records matching the specified criteria in the database."
            
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
            
            # Handle single value responses (no chart needed)
            if chart_type == "none" and len(df) == 1 and len(df.columns) == 1:
                value = df.iloc[0, 0]
                col_name = df.columns[0]
                if isinstance(value, (int, float)):
                    return f"The result is {value:,} for {col_name}. This represents the total count or value for your query about the commercial licensing data."
                else:
                    return f"The result is {value} for {col_name}."
            
            # Handle insight type for single values (legacy support)
            if chart_type == "insight" and len(df) == 1 and len(df.columns) == 1:
                value = df.iloc[0, 0]
                col_name = df.columns[0]
                return f"The result is {value:,} for {col_name}. This represents the total count or value for your query about the commercial licensing data."
            
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
            if df.empty:
                return "No data available for this question. The query executed successfully but found no records matching the specified criteria in the database."
            return f"Data shows {len(df)} records. Chart type '{chart_type}' is suitable for visualizing this data distribution."
    
    def get_table_schema(self, table_name: str) -> str:
        """Get detailed schema information for a specific Oracle materialized view"""
        try:
            # Try LangChain method first if available
            if self.db:
                return self.db.get_table_info_no_throw([table_name])
        except:
            pass
        
        try:
            # Use direct Oracle connection for schema query
            cursor = self.oracle_connection.cursor()
            
            # Parse schema and table name from full name (e.g., AI_USER.COMMERCIAL_LICENSE_MV)
            if '.' in table_name:
                schema, table = table_name.split('.', 1)
            else:
                schema = 'AI_USER'
                table = table_name
            
            print(f"Debug - Querying schema for: schema='{schema}', table='{table}'")
            
            # Use simpler query without bind variables to avoid ORA-01745
            schema_query = f"""
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE,
                    DATA_DEFAULT
                FROM ALL_TAB_COLUMNS 
                WHERE OWNER = '{schema}' 
                AND TABLE_NAME = '{table}'
                ORDER BY COLUMN_ID
            """
            
            print(f"Debug - Executing schema query: {schema_query}")
            cursor.execute(schema_query)
            
            columns = cursor.fetchall()
            print(f"Debug - Found {len(columns)} columns")
            
            if not columns:
                cursor.close()
                return f"Materialized View: {table_name}\nError: No columns found or access denied"
            
            schema_info = f"Materialized View: {table_name}\nColumns:\n"
            for col_name, data_type, data_length, data_precision, data_scale, nullable, default in columns:
                # Format data type with length/precision
                if data_type in ['VARCHAR2', 'CHAR'] and data_length:
                    type_info = f"{data_type}({data_length})"
                elif data_type == 'NUMBER' and data_precision:
                    if data_scale and data_scale > 0:
                        type_info = f"{data_type}({data_precision},{data_scale})"
                    else:
                        type_info = f"{data_type}({data_precision})"
                else:
                    type_info = data_type
                
                nullable_info = "NULL" if nullable == "Y" else "NOT NULL"
                default_info = f" DEFAULT {default}" if default else ""
                schema_info += f"  - {col_name}: {type_info} {nullable_info}{default_info}\n"
            
            # Add row count information
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                schema_info += f"\nRow Count: {row_count:,}\n"
            except Exception as count_error:
                print(f"Debug - Could not get row count: {count_error}")
                schema_info += f"\nRow Count: Unable to retrieve\n"
            
            cursor.close()
            print(f"Debug - Schema info successfully retrieved")
            return schema_info
            
        except Exception as e:
            print(f"Debug - Schema query error: {str(e)}")
            return f"Materialized View: {table_name}\nError getting schema: {str(e)}"
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get information about all available materialized views"""
        tables = self.materialized_views
        table_schemas = {}
        
        for table in tables:
            try:
                schema_info = self.get_table_schema(table)
                table_schemas[table] = schema_info
            except Exception:
                table_schemas[table] = "Schema information not available"
        
        return {
            "tables": tables,
            "table_schemas": table_schemas
        }
    
    def test_oracle_connection(self) -> bool:
        """Test Oracle database connection and materialized view access"""
        try:
            cursor = self.oracle_connection.cursor()
            
            # Test basic connection
            cursor.execute("SELECT SYSDATE FROM DUAL")
            sysdate = cursor.fetchone()
            print(f"✅ Oracle connection successful. Current time: {sysdate[0]}")
            
            # Test each materialized view
            for mv_name in self.materialized_views:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {mv_name}")
                    count = cursor.fetchone()[0]
                    print(f"✅ {mv_name}: {count:,} rows")
                except Exception as e:
                    print(f"❌ {mv_name}: Error - {str(e)}")
            
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ Oracle connection failed: {str(e)}")
            return False 