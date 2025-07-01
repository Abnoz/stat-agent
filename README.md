# LangChain SQL Query Agent API

A powerful FastAPI-based service that converts natural language questions into SQL queries against your PostgreSQL database and returns chart-ready data for visualization using Azure OpenAI.

## Features

- 🤖 Natural language to SQL query conversion using LangChain + Azure OpenAI
- 📊 Chart-ready data output (bar, line, pie, table formats)
- 🚀 FastAPI REST API with automatic documentation
- 🔄 Automatic chart type detection
- 📈 Support for time series data
- 🛡️ Input validation and error handling
- 🗄️ Database schema introspection
- 📝 Interactive API documentation
- ☁️ Azure OpenAI integration

## Prerequisites

- Python 3.8+
- PostgreSQL database
- Azure OpenAI service with deployed model

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

3. **Start the API server:**
   ```bash
   uvicorn main:app --reload
   ```

4. **Access the API:**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## API Endpoints

### Core Endpoints

- `POST /query` - Execute natural language query and get chart data
- `GET /database/info` - Get database schema information
- `GET /database/tables` - List available tables
- `GET /examples` - Get example queries for different chart types
- `GET /health` - Health check endpoint

### Query Endpoint

```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "How many users are registered each month?",
       "chart_type": "line"
     }'
```

Response format:
```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2024-01-01T00:00:00",
      "value": 150,
      "metric": "user_count"
    }
  ],
  "chart_type": "line",
  "query": "SELECT DATE_TRUNC('month', created_at) as month, COUNT(*) as user_count FROM users GROUP BY month ORDER BY month",
  "message": "Query executed successfully"
}
```

## Chart Data Formats

### Bar/Pie Charts
```json
{
  "data": [
    {
      "label": "Product A",
      "value": 1250.50,
      "category": "Electronics"
    }
  ],
  "chart_type": "bar"
}
```

### Line Charts (Time Series)
```json
{
  "data": [
    {
      "timestamp": "2024-01-01T00:00:00",
      "value": 150,
      "metric": "sales"
    }
  ],
  "chart_type": "line"
}
```

### Table Data
```json
{
  "data": {
    "columns": ["id", "name", "email", "created_at"],
    "rows": [
      [1, "John Doe", "john@example.com", "2024-01-01"]
    ]
  },
  "chart_type": "table"
}
```

## Using the API

### Python Client Example

```python
import requests

base_url = "http://localhost:8000"

# Query for chart data
response = requests.post(f"{base_url}/query", json={
    "question": "Show me the top 10 products by revenue",
    "chart_type": "bar"
})

data = response.json()
if data["success"]:
    chart_data = data["data"]
    chart_type = data["chart_type"]
    # Use chart_data with your preferred charting library
```

### JavaScript/Frontend Example

```javascript
const response = await fetch('http://localhost:8000/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    question: 'What are the monthly sales trends?',
    chart_type: 'line'
  })
});

const result = await response.json();
if (result.success) {
  // Use result.data with Chart.js, D3, or any charting library
  console.log('Chart type:', result.chart_type);
  console.log('Data:', result.data);
}
```

## Chart Types

- `auto` - Automatically detect the best chart type
- `bar` - Bar chart for comparisons
- `line` - Line chart for time series data
- `pie` - Pie chart for proportions/distributions
- `table` - Table view for detailed data

## Example Questions

### Bar Charts
- "What are the top 10 customers by revenue?"
- "Show me sales by product category"
- "Which departments have the most employees?"

### Line Charts
- "How have sales changed over time?"
- "Show user registrations by month"
- "What's the daily order volume trend?"

### Pie Charts
- "What's the distribution of user roles?"
- "Show market share by region"
- "Break down orders by payment method"

### Tables
- "List all orders from the last 30 days"
- "Show customer details for VIP customers"
- "Display product inventory levels"

## Development

### Run with auto-reload:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Test the API:
```bash
python test_client.py
```

## Project Structure

```
├── main.py                  # FastAPI application
├── sql_agent_service.py     # Core SQL agent service
├── schemas.py              # Pydantic models for API
├── config.py               # Configuration management
├── test_client.py          # API client for testing
├── requirements.txt        # Dependencies
├── .env.example           # Environment template
└── README.md             # This file
```

## Chart Integration Examples

### Chart.js Integration
```javascript
// For bar charts
const chartData = {
  labels: data.map(item => item.label),
  datasets: [{
    data: data.map(item => item.value),
    backgroundColor: 'rgba(54, 162, 235, 0.2)',
    borderColor: 'rgba(54, 162, 235, 1)'
  }]
};

// For line charts (time series)
const timeSeriesData = {
  labels: data.map(item => new Date(item.timestamp).toLocaleDateString()),
  datasets: [{
    label: data[0]?.metric || 'Value',
    data: data.map(item => item.value),
    borderColor: 'rgb(75, 192, 192)',
    tension: 0.1
  }]
};
```

### D3.js Integration
```javascript
// The API data format is designed to work seamlessly with D3
d3.json("http://localhost:8000/query", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({
    question: "Show sales by month",
    chart_type: "line"
  })
}).then(result => {
  const data = result.data;
  // Use data directly with D3 scales and visualization
});
```

## Environment Variables

```env
# Required
OPENAI_API_KEY=your_openai_api_key

# Database (choose one method)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# OR individual settings
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password

# Optional
LLM_MODEL=gpt-3.5-turbo
LLM_TEMPERATURE=0
```

## Security Notes

- The API runs in read-only mode by default
- Input validation prevents SQL injection
- Environment-based configuration
- CORS enabled for frontend integration

## Troubleshooting

### API won't start
- Check your `.env` file configuration
- Verify database connectivity
- Ensure OpenAI API key is valid

### Queries failing
- Check database table names and schemas
- Verify the question is clear and specific
- Review the generated SQL query in the response

### Chart data issues
- Ensure your data has appropriate columns for the chart type
- Time series charts need date/timestamp columns
- Numerical values are required for chart visualization

## Contributing

Feel free to submit issues and enhancement requests! # stat-agent
