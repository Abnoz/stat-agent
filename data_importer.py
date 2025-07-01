import pandas as pd
import numpy as np
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import re
from typing import Dict, List, Any

load_dotenv()

class DataImporter:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            self.db_url = self._build_database_url()
        self.engine = create_engine(self.db_url)
    
    def _build_database_url(self):
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME')
        username = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    def read_excel_file(self, file_path: str, sheet_name: str = None) -> pd.DataFrame:
        """Read Excel file and return DataFrame"""
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            
            print(f"Successfully loaded Excel file with {len(df)} rows and {len(df.columns)} columns")
            print(f"Columns: {list(df.columns)}")
            return df
        except Exception as e:
            raise Exception(f"Error reading Excel file: {str(e)}")
    
    def clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize column names"""
        df_cleaned = df.copy()
        
        new_columns = []
        for col in df_cleaned.columns:
            clean_col = str(col).strip()
            clean_col = re.sub(r'[^\w\s]', '', clean_col)
            clean_col = re.sub(r'\s+', '_', clean_col)
            clean_col = clean_col.lower()
            clean_col = re.sub(r'[^a-zA-Z0-9_]', '', clean_col)
            if clean_col == '' or clean_col == 'nan':
                clean_col = f'column_{len(new_columns)}'
            
            # Handle 'id' column conflict - rename to original_id
            if clean_col == 'id':
                clean_col = 'original_id'
                print(f"Renamed 'id' column to 'original_id' to avoid conflict with auto-generated primary key")
            
            # Ensure unique column names
            original_clean_col = clean_col
            counter = 1
            while clean_col in new_columns:
                clean_col = f"{original_clean_col}_{counter}"
                counter += 1
            
            new_columns.append(clean_col)
        
        df_cleaned.columns = new_columns
        print(f"Cleaned column names: {list(df_cleaned.columns)}")
        return df_cleaned
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean the data - remove duplicates, handle missing values, standardize formats"""
        df_cleaned = df.copy()
        
        print(f"Original data shape: {df_cleaned.shape}")
        
        # Remove completely empty rows
        df_cleaned = df_cleaned.dropna(how='all')
        print(f"After removing empty rows: {df_cleaned.shape}")
        
        # Remove duplicate rows
        initial_rows = len(df_cleaned)
        df_cleaned = df_cleaned.drop_duplicates()
        duplicates_removed = initial_rows - len(df_cleaned)
        if duplicates_removed > 0:
            print(f"Removed {duplicates_removed} duplicate rows")
        
        # Clean text columns
        for col in df_cleaned.columns:
            if df_cleaned[col].dtype == 'object':
                df_cleaned[col] = df_cleaned[col].astype(str)
                df_cleaned[col] = df_cleaned[col].str.strip()
                df_cleaned[col] = df_cleaned[col].replace('nan', None)
                df_cleaned[col] = df_cleaned[col].replace('', None)
        
        # Convert numeric columns
        for col in df_cleaned.columns:
            if df_cleaned[col].dtype == 'object':
                # Try to convert to numeric if possible
                numeric_series = pd.to_numeric(df_cleaned[col], errors='coerce')
                if not numeric_series.isna().all():
                    non_null_count = numeric_series.notna().sum()
                    total_count = len(df_cleaned[col].dropna())
                    if non_null_count / total_count > 0.8:  # If 80% can be converted to numeric
                        df_cleaned[col] = numeric_series
                        print(f"Converted column '{col}' to numeric")
        
        # Handle date columns
        for col in df_cleaned.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    df_cleaned[col] = pd.to_datetime(df_cleaned[col], errors='coerce')
                    print(f"Converted column '{col}' to datetime")
                except:
                    pass
        
        print(f"Final cleaned data shape: {df_cleaned.shape}")
        print(f"Data types after cleaning:")
        for col, dtype in df_cleaned.dtypes.items():
            print(f"  {col}: {dtype}")
        
        return df_cleaned
    
    def create_table(self, df: pd.DataFrame, table_name: str = 'commercial') -> str:
        """Create table schema based on DataFrame"""
        columns_sql = []
        
        for col, dtype in df.dtypes.items():
            if dtype == 'object':
                sql_type = 'TEXT'
            elif dtype in ['int64', 'int32']:
                # Use BIGINT to handle large integer values and prevent overflow
                sql_type = 'BIGINT'
            elif dtype in ['float64', 'float32']:
                sql_type = 'DECIMAL(15,4)'
            elif dtype == 'datetime64[ns]':
                sql_type = 'TIMESTAMP'
            elif dtype == 'bool':
                sql_type = 'BOOLEAN'
            else:
                sql_type = 'TEXT'
            
            columns_sql.append(f'"{col}" {sql_type}')
        
        # Add an ID column
        create_sql = f'''
        DROP TABLE IF EXISTS {table_name} CASCADE;
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            {', '.join(columns_sql)},
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        '''
        
        return create_sql
    
    def import_to_db(self, df, table_name):
        try:
            total_rows = len(df)
            batch_size = 100  # Reduced from 1000 to handle more columns
            imported_rows = 0
            
            print(f"\n📊 Starting import of {total_rows} rows...")
            print(f"Using batch size: {batch_size}")
            print(f"Number of columns: {len(df.columns)}")
            
            for start_idx in range(0, total_rows, batch_size):
                end_idx = min(start_idx + batch_size, total_rows)
                batch_df = df.iloc[start_idx:end_idx]
                
                batch_num = start_idx // batch_size + 1
                total_batches = (total_rows - 1) // batch_size + 1
                
                print(f"Importing batch {batch_num}/{total_batches} (rows {start_idx+1}-{end_idx})...")
                
                try:
                    batch_df.to_sql(
                        table_name, 
                        self.engine, 
                        if_exists='append', 
                        index=False, 
                        method='multi',
                        chunksize=50  # Further break down within pandas
                    )
                    
                    imported_rows += len(batch_df)
                    print(f"✅ Batch {batch_num} imported successfully. Progress: {imported_rows}/{total_rows} rows")
                    
                except Exception as batch_error:
                    print(f"❌ Error in batch {batch_num}: {str(batch_error)}")
                    
                    # Try even smaller chunks for this batch
                    print(f"🔄 Retrying batch {batch_num} with smaller chunks...")
                    small_chunk_size = 25
                    batch_imported = 0
                    
                    for chunk_start in range(0, len(batch_df), small_chunk_size):
                        chunk_end = min(chunk_start + small_chunk_size, len(batch_df))
                        chunk_df = batch_df.iloc[chunk_start:chunk_end]
                        
                        try:
                            chunk_df.to_sql(
                                table_name, 
                                self.engine, 
                                if_exists='append', 
                                index=False, 
                                method='multi'
                            )
                            batch_imported += len(chunk_df)
                            print(f"  ✅ Small chunk {chunk_start//small_chunk_size + 1} imported ({len(chunk_df)} rows)")
                        except Exception as chunk_error:
                            print(f"  ❌ Failed to import chunk: {str(chunk_error)}")
                            print(f"  Skipping {len(chunk_df)} rows...")
                    
                    imported_rows += batch_imported
                    print(f"📊 Batch {batch_num} recovery complete. Imported {batch_imported}/{len(batch_df)} rows from this batch.")
                
            print(f"\n🎉 Import completed!")
            print(f"Total rows imported: {imported_rows}/{total_rows}")
            if imported_rows < total_rows:
                print(f"⚠️  Warning: {total_rows - imported_rows} rows were skipped due to errors")
            
        except Exception as e:
            print(f"❌ Critical error during import: {str(e)}")
            print(f"Successfully imported {imported_rows} rows before error occurred")
            raise
    
    def import_excel_to_db(self, excel_file_path: str, table_name: str = 'commercial', sheet_name: str = None):
        """Complete process: read Excel, clean data, create table, import data"""
        try:
            # Step 1: Read Excel file
            print("Step 1: Reading Excel file...")
            df = self.read_excel_file(excel_file_path, sheet_name)
            
            # Step 2: Clean column names
            print("\nStep 2: Cleaning column names...")
            df = self.clean_column_names(df)
            
            # Step 3: Clean data
            print("\nStep 3: Cleaning data...")
            df = self.clean_data(df)
            
            # Step 4: Create table
            print(f"\nStep 4: Creating table '{table_name}'...")
            create_sql = self.create_table(df, table_name)
            
            with self.engine.connect() as conn:
                conn.execute(text(create_sql))
                conn.commit()
            print(f"Table '{table_name}' created successfully")
            
            # Step 5: Import data
            print(f"\nStep 5: Importing data to table '{table_name}'...")
            self.import_to_db(df, table_name)
            
            # Step 6: Show summary
            self.show_import_summary(table_name)
            
        except Exception as e:
            print(f"❌ Error during import: {str(e)}")
            raise
    
    def show_import_summary(self, table_name: str):
        """Show summary of imported data"""
        with self.engine.connect() as conn:
            # Count rows
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.scalar()
            
            # Get column info
            result = conn.execute(text(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            
            print(f"\n📊 Import Summary for '{table_name}':")
            print(f"   Total rows: {row_count}")
            print(f"   Total columns: {len(columns)}")
            print(f"   Columns:")
            for col_name, col_type in columns:
                print(f"     - {col_name}: {col_type}")
    
    def preview_data(self, table_name: str = 'commercial', limit: int = 5):
        """Preview imported data"""
        with self.engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
            rows = result.fetchall()
            columns = result.keys()
            
            print(f"\n👀 Preview of '{table_name}' (first {limit} rows):")
            print("-" * 100)
            
            # Print headers
            print(" | ".join([f"{col[:15]:15}" for col in columns]))
            print("-" * 100)
            
            # Print data rows
            for row in rows:
                print(" | ".join([f"{str(val)[:15]:15}" if val is not None else f"{'NULL':15}" for val in row]))

if __name__ == "__main__":
    importer = DataImporter()
    
    # You can run this script directly with your Excel file
    excel_file = input("Enter the path to your commercial Excel file: ").strip()
    
    if os.path.exists(excel_file):
        importer.import_excel_to_db(excel_file, 'commercial')
        importer.preview_data('commercial')
    else:
        print(f"File not found: {excel_file}") 