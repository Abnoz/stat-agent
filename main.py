from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from sql_agent_service import SQLAgentService
from schemas import (
    QueryRequest, 
    QueryResponse, 
    DatabaseInfo, 
    ErrorResponse,
    ChartDataPoint,
    TimeSeriesDataPoint,
    TableData
)
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sql_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sql_service
    try:
        Config.validate()
        sql_service = SQLAgentService()
        logger.info("SQL Agent Service initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize SQL Agent Service: {str(e)}")
        yield
    finally:
        sql_service = None

app = FastAPI(
    title="Commercial Licensing Data Analysis API",
    description="AI-powered commercial licensing data analysis API that generates insights and chart-ready data from commercial license databases",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_sql_service():
    if sql_service is None:
        raise HTTPException(status_code=503, detail="SQL Agent Service is not available")
    return sql_service

@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "Commercial Licensing Data Analysis API",
        "status": "active",
        "version": "1.0.0",
        "description": "AI-powered analysis of commercial licensing data"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    try:
        service = get_sql_service()
        return {"status": "healthy", "database_connected": True}
    except Exception:
        return {"status": "unhealthy", "database_connected": False}

@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def execute_query(
    request: QueryRequest,
    service: SQLAgentService = Depends(get_sql_service)
):
    try:
        result = await service.query(request.question, request.chart_type)
        return result
    except Exception as e:
        logger.error(f"Query execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database/info", response_model=DatabaseInfo, tags=["Database"])
async def get_database_info(service: SQLAgentService = Depends(get_sql_service)):
    try:
        info = service.get_database_info()
        return DatabaseInfo(
            tables=info["tables"],
            table_schemas=info["table_schemas"]
        )
    except Exception as e:
        logger.error(f"Failed to get database info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database/tables", tags=["Database"])
async def get_tables(service: SQLAgentService = Depends(get_sql_service)):
    try:
        info = service.get_database_info()
        return {"tables": info["tables"]}
    except Exception as e:
        logger.error(f"Failed to get tables: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/examples", tags=["Examples"])
async def get_example_queries():
    return {
        "examples": [
            {
                "question": "How many commercial licenses were issued each month?",
                "chart_type": "line",
                "description": "Time series chart showing commercial license issuance trends over time"
            },
            {
                "question": "What are the top 10 business types by number of licenses?",
                "chart_type": "bar",
                "description": "Bar chart showing most common business types"
            },
            {
                "question": "Show the distribution of license statuses",
                "chart_type": "pie",
                "description": "Pie chart showing active vs inactive vs pending licenses"
            },
            {
                "question": "List all licenses issued in the last 30 days",
                "chart_type": "table",
                "description": "Table view of recent commercial licenses"
            },
            {
                "question": "What's the average license fee by business category?",
                "chart_type": "bar",
                "description": "Bar chart comparing license fees across business categories"
            },
            {
                "question": "Which zip codes have the most commercial licenses?",
                "chart_type": "bar",
                "description": "Geographic distribution of commercial licenses"
            },
            {
                "question": "Show license renewal patterns by year",
                "chart_type": "line",
                "description": "Time series showing license renewal trends"
            },
            {
                "question": "How many new businesses opened each quarter?",
                "chart_type": "bar",
                "description": "Quarterly business formation analysis"
            }
        ],
        "chart_types": ["auto", "bar", "line", "pie", "table"],
        "data_focus": "Commercial licensing data including business types, license statuses, fees, geographic distribution, and temporal patterns"
    }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=str(exc),
            message="An unexpected error occurred"
        ).dict()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 