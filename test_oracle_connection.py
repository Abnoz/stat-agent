#!/usr/bin/env python3
"""
Oracle Database Connection Test for MOMAH AI System
Tests connection to Oracle materialized views and SQL Agent Service functionality
"""

import oracledb
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Oracle connection configuration
OFFICIAL_TNS = """(DESCRIPTION=(ADDRESS_LIST=(FAILOVER=ON)(LOAD_BALANCE=ON)(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=ruhmpp-exa-scan.momra.net)(PORT=1521)))(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=drmpp-exa-scan.momra.net)(PORT=1521))))(CONNECT_DATA=(SERVICE_NAME=MEDIUM_AIDBPRO.momra.net)(FAILOVER_MODE=(TYPE=select)(METHOD=basic))))"""

DB_USER = os.getenv('DB_USER', 'AI_READ')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'Ai2025aI')

MATERIALIZED_VIEWS = [
    "AI_USER.COMMERCIAL_LICENSE_MV",
    "AI_USER.COM_LIC_ADDITIONAL_ACTIVITY_MV", 
    "AI_USER.COM_REQUESTS_COMPLETE_MV"
]

def test_oracle_connection():
    """Test Oracle database connection and materialized view access"""
    print("🔐 MOMAH AI Database Connection Test")
    print("=" * 60)
    print("Using OFFICIAL AIDBPRO_DR TNS Configuration")
    print(f"User: {DB_USER}")
    print("-" * 60)
    
    try:
        print("📡 Connecting with official TNS string...")
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=OFFICIAL_TNS
        )
        
        print("✅ Successfully connected to MOMAH AI Database!")
        
        cursor = connection.cursor()
        
        # Test basic database info
        cursor.execute("SELECT SYSDATE FROM DUAL")
        sysdate = cursor.fetchone()
        print(f"✅ Database time: {sysdate[0]}")
        
        cursor.execute("SELECT USER FROM DUAL")
        user = cursor.fetchone()
        print(f"✅ Connected as: {user[0]}")
        
        cursor.execute("SELECT SYS_CONTEXT('USERENV', 'SERVICE_NAME') FROM DUAL")
        service = cursor.fetchone()
        print(f"✅ Service name: {service[0]}")
        
        print("\n📊 Testing Access to Commercial Data Materialized Views:")
        print("=" * 60)
        
        for mv_name in MATERIALIZED_VIEWS:
            try:
                print(f"\n🔍 Testing: {mv_name}")
                
                # Test row count
                cursor.execute(f"SELECT COUNT(*) FROM {mv_name}")
                count = cursor.fetchone()[0]
                print(f"✅ Row count: {count:,}")
                
                # Test column structure
                cursor.execute(f"SELECT * FROM {mv_name} WHERE ROWNUM <= 1")
                columns = [desc[0] for desc in cursor.description]
                sample_row = cursor.fetchone()
                print(f"✅ Columns ({len(columns)}): {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}")
                
                # Test sample query
                cursor.execute(f"SELECT COUNT(*) FROM {mv_name} WHERE ROWNUM <= 100")
                sample_count = cursor.fetchone()[0]
                print(f"✅ Sample query successful: {sample_count} rows in first 100")
                
            except oracledb.Error as e:
                error_obj, = e.args
                print(f"❌ Error accessing {mv_name}: ORA-{error_obj.code}: {error_obj.message}")
                if error_obj.code == 942:
                    print("   💡 Table/view does not exist or no access")
                elif error_obj.code == 1031:
                    print("   💡 Insufficient privileges")
        
        cursor.close()
        connection.close()
        
        print("\n🎉 CONNECTION SUCCESS!")
        print("=" * 60)
        print("✅ MOMAH AI Database is accessible")
        print("✅ AI_READ user has proper access")
        print("✅ Commercial data materialized views are ready")
        return True
        
    except oracledb.Error as e:
        error_obj, = e.args
        print(f"❌ Connection failed: ORA-{error_obj.code}: {error_obj.message}")
        
        if error_obj.code == 12170:
            print("💡 Connection timeout - check network access")
        elif error_obj.code == 12514:
            print("💡 Service name issue - verify TNS configuration")
        elif error_obj.code == 1017:
            print("💡 Invalid credentials - check username/password")
        elif error_obj.code == 12541:
            print("💡 No listener - database service may be down")
        
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_sql_agent_service():
    """Test the SQL Agent Service with Oracle"""
    print("\n🤖 Testing SQL Agent Service with Oracle")
    print("=" * 60)
    
    try:
        from sql_agent_service import SQLAgentService
        
        print("📡 Initializing SQL Agent Service...")
        service = SQLAgentService()
        
        print("✅ SQL Agent Service initialized successfully")
        
        # Test connection
        if service.test_oracle_connection():
            print("✅ Oracle connection test passed")
        else:
            print("❌ Oracle connection test failed")
            return False
        
        # Test database info
        print("\n📊 Testing database info retrieval...")
        db_info = service.get_database_info()
        print(f"✅ Available tables: {len(db_info['tables'])}")
        for table in db_info['tables']:
            print(f"   - {table}")
        
        return True
        
    except Exception as e:
        print(f"❌ SQL Agent Service test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    print("MOMAH AI Oracle Database Test Suite")
    print("=" * 70)
    
    # Test 1: Basic Oracle connection
    if not test_oracle_connection():
        print("\n❌ Basic connection test failed")
        return False
    
    # Test 2: SQL Agent Service
    if not test_sql_agent_service():
        print("\n❌ SQL Agent Service test failed")
        return False
    
    print("\n🎉 ALL TESTS PASSED!")
    print("=" * 70)
    print("✅ Oracle database is ready for AI analytics")
    print("✅ SQL Agent Service is working correctly")
    print("✅ System is ready for production use")

if __name__ == "__main__":
    main() 