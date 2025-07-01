import requests
import json
from typing import Dict, Any

class SQLAgentClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
    
    def health_check(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def get_database_info(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/database/info")
        response.raise_for_status()
        return response.json()
    
    def get_tables(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/database/tables")
        response.raise_for_status()
        return response.json()
    
    def query(self, question: str, chart_type: str = "auto") -> Dict[str, Any]:
        payload = {
            "question": question,
            "chart_type": chart_type
        }
        response = requests.post(f"{self.base_url}/query", json=payload)
        response.raise_for_status()
        return response.json()
    
    def get_examples(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/examples")
        response.raise_for_status()
        return response.json()

def demo_usage():
    client = SQLAgentClient()
    
    try:
        print("=== SQL Agent API Demo ===")
        
        health = client.health_check()
        print(f"Health Status: {health}")
        
        if health.get("status") != "healthy":
            print("API is not healthy. Please check your configuration.")
            return
        
        print("\n1. Getting database information...")
        try:
            db_info = client.get_database_info()
            print(f"Available tables: {db_info.get('tables', [])}")
        except Exception as e:
            print(f"Error getting database info: {e}")
            return
        
        print("\n2. Getting example queries...")
        examples = client.get_examples()
        print("Example queries:")
        for i, example in enumerate(examples.get("examples", []), 1):
            print(f"{i}. {example['question']} ({example['chart_type']})")
        
        print("\n3. Testing queries...")
        test_queries = [
            ("How many records are in each table?", "bar"),
            ("Show me the first 5 rows from the first table", "table"),
        ]
        
        for question, chart_type in test_queries:
            print(f"\nTesting: {question}")
            try:
                result = client.query(question, chart_type)
                print(f"Success: {result['success']}")
                print(f"Chart Type: {result['chart_type']}")
                print(f"Message: {result['message']}")
                
                if result['success'] and result['data']:
                    data = result['data']
                    if isinstance(data, list) and len(data) > 0:
                        print(f"Data points: {len(data)}")
                        print(f"Sample data: {data[0] if data else 'None'}")
                    elif isinstance(data, dict) and 'columns' in data:
                        print(f"Table columns: {data['columns']}")
                        print(f"Table rows: {len(data.get('rows', []))}")
                
                if result.get('error'):
                    print(f"Error: {result['error']}")
                    
            except Exception as e:
                print(f"Query failed: {e}")
        
        print("\n=== Interactive Mode ===")
        print("Enter your questions (or 'quit' to exit):")
        
        while True:
            try:
                question = input("\nYour question: ").strip()
                if question.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not question:
                    continue
                
                chart_type = input("Chart type (auto/bar/line/pie/table) [auto]: ").strip() or "auto"
                
                result = client.query(question, chart_type)
                
                print(f"\nResult:")
                print(f"Success: {result['success']}")
                print(f"Chart Type: {result['chart_type']}")
                print(f"SQL Query: {result.get('query', 'Not available')}")
                print(f"Message: {result['message']}")
                
                if result['success'] and result['data']:
                    print("\nChart Data Preview:")
                    data = result['data']
                    if isinstance(data, list):
                        print(f"Data points: {len(data)}")
                        for i, point in enumerate(data[:3]):
                            print(f"  {i+1}. {point}")
                        if len(data) > 3:
                            print(f"  ... and {len(data) - 3} more points")
                    elif isinstance(data, dict):
                        print(f"Table: {len(data.get('rows', []))} rows × {len(data.get('columns', []))} columns")
                        if data.get('columns'):
                            print(f"Columns: {', '.join(data['columns'])}")
                
                if result.get('error'):
                    print(f"Error: {result['error']}")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    except requests.exceptions.ConnectionError:
        print("Cannot connect to the API. Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"Demo failed: {e}")

if __name__ == "__main__":
    demo_usage() 