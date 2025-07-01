#!/usr/bin/env python3

import os
import sys
from data_importer import DataImporter
import pandas as pd

def main():
    print("🏢 Commercial Data Importer")
    print("=" * 50)
    
    importer = DataImporter()
    
    # Check if running in Docker (Excel file should be mounted)
    excel_file_path = None
    
    # First, check for the mounted Excel file in Docker
    if os.path.exists('/app/Commercial_Licenses.xlsx'):
        excel_file_path = '/app/Commercial_Licenses.xlsx'
        print(f"📁 Found mounted Excel file: {excel_file_path}")
    
    # If not in Docker, look for Excel files in current directory
    if not excel_file_path:
        current_dir = os.getcwd()
        excel_files = []
        
        for file in os.listdir(current_dir):
            if file.lower().endswith(('.xlsx', '.xls')) and 'commercial' in file.lower():
                excel_files.append(file)
        
        if excel_files:
            print("📋 Found Excel files containing 'commercial':")
            for i, file in enumerate(excel_files, 1):
                print(f"   {i}. {file}")
            
            if len(excel_files) == 1:
                excel_file_path = excel_files[0]
                print(f"✅ Using: {excel_file_path}")
            else:
                try:
                    choice = input("\nSelect file number (or press Enter for 1): ").strip()
                    if not choice:
                        choice = "1"
                    file_index = int(choice) - 1
                    if 0 <= file_index < len(excel_files):
                        excel_file_path = excel_files[file_index]
                    else:
                        print("❌ Invalid selection")
                        return
                except (ValueError, KeyboardInterrupt):
                    print("❌ Invalid input")
                    return
        else:
            try:
                excel_file_path = input("📂 Enter the full path to your commercial Excel file: ").strip()
            except KeyboardInterrupt:
                print("\n❌ Operation cancelled")
                return
    
    if not excel_file_path or not os.path.exists(excel_file_path):
        print(f"❌ File not found: {excel_file_path}")
        return
    
    # Check if file has multiple sheets
    try:
        excel_file = pd.ExcelFile(excel_file_path)
        sheets = excel_file.sheet_names
        
        sheet_name = None
        if len(sheets) > 1:
            print(f"\n📊 Found {len(sheets)} sheets:")
            for i, sheet in enumerate(sheets, 1):
                print(f"   {i}. {sheet}")
            
            try:
                choice = input("Select sheet number (or press Enter for 1): ").strip()
                if not choice:
                    choice = "1"
                sheet_index = int(choice) - 1
                if 0 <= sheet_index < len(sheets):
                    sheet_name = sheets[sheet_index]
                else:
                    print("❌ Invalid selection, using first sheet")
                    sheet_name = sheets[0]
            except (ValueError, KeyboardInterrupt):
                print("❌ Using first sheet")
                sheet_name = sheets[0]
        else:
            sheet_name = sheets[0]
        
        print(f"📋 Using sheet: {sheet_name}")
        
    except Exception as e:
        print(f"❌ Error reading Excel file: {str(e)}")
        return
    
    # Import the data
    print(f"\n🚀 Starting import process...")
    try:
        importer.import_excel_to_db(excel_file_path, 'commercial', sheet_name)
        print("\n✅ Import completed successfully!")
        
        # Preview the data
        print("\n👀 Preview of imported data:")
        importer.preview_data('commercial', 10)
        
    except Exception as e:
        print(f"\n❌ Import failed: {str(e)}")
        return

if __name__ == "__main__":
    main() 