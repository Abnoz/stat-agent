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
        
        if len(df.columns) == 1 and len(df) == 1:
            count_keywords = ['count', 'total', 'number', 'how many', 'عدد', 'إجمالي', 'كم', 'مجموع']
            if any(word in question_lower for word in count_keywords):
                return "insight"
        
        if len(df.columns) == 1:
            return "insight"
        
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
        # Handle insight type for single values
        if chart_type == "insight":
            # For insight type, return the data in table format for easy extraction
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
            schema_info = self.get_table_schema(self.main_table)
            
            prompt = f"""Generate a valid Oracle SQL SELECT statement to answer the question using the database schema below.

Database Schema for '{self.main_table}':
{schema_info}

Question: {question}

Requirements:
1. Start with SELECT keyword
2. Use ONLY column names from the schema above
3. Use table name: {self.main_table}
4. For counts: SELECT COUNT(*) as total_count FROM {self.main_table}
5. For breakdowns: SELECT column_name, COUNT(*) as count FROM {self.main_table} GROUP BY column_name
6. No semicolons at the end
7. Valid Oracle SQL syntax

Example for total count: SELECT COUNT(*) as total_licenses FROM {self.main_table}

Generate the SELECT statement:"""

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
            
            # Remove any extra whitespace and newlines
            sql_query = ' '.join(sql_query.split())
            sql_query = sql_query.strip()
            
            print(f"Debug - Cleaned SQL query: '{sql_query}'")
            
            # If the query doesn't start with SELECT, try to fix it
            if not sql_query.upper().startswith(('SELECT', 'WITH')):
                # Try to extract SELECT from the response
                select_match = re.search(r'(SELECT\s+.*)', sql_query, re.IGNORECASE | re.DOTALL)
                if select_match:
                    sql_query = select_match.group(1).strip()
                    print(f"Debug - Extracted SELECT query: '{sql_query}'")
                else:
                    # Generate a simple count query as fallback
                    sql_query = f"SELECT COUNT(*) as total_count FROM {self.main_table}"
                    print(f"Debug - Using fallback query: '{sql_query}'")
            
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
                cursor.execute(sql_query)
                
                # Fetch results and convert to DataFrame
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                cursor.close()
                
                df = pd.DataFrame(rows, columns=columns)
                print(f"Debug - Query returned {len(df)} rows using direct Oracle connection")
                
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
                print(f"Debug - Oracle data processing error: {str(data_error)}")
                return QueryResponse(
                    success=False,
                    data=None,
                    chart_type="table",
                    insights=None,
                    message="Failed to process Oracle query results",
                    error=str(data_error)
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
            
            # Handle single value responses (insight type)
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
            
            cursor.execute("""
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE,
                    DATA_DEFAULT
                FROM ALL_TAB_COLUMNS 
                WHERE OWNER = :schema 
                AND TABLE_NAME = :table
                ORDER BY COLUMN_ID
            """, {'schema': schema, 'table': table})
            
            columns = cursor.fetchall()
            
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
            except:
                schema_info += f"\nRow Count: Unable to retrieve\n"
            
            cursor.close()
            return schema_info
            
        except Exception as e:
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