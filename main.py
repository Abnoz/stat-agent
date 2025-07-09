from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
from sql_agent_service import SQLAgentService
from schemas import (
    QueryRequest, 
    QueryResponse, 
    DatabaseInfo, 
    ErrorResponse,
    ChartDataPoint,
    TimeSeriesDataPoint,
    TableData,
    JobStatusResponse
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
    title="SQL Agent API",
    description="Natural language to SQL query conversion with chart-ready data output",
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

def get_sql_service() -> SQLAgentService:
    if sql_service is None:
        raise HTTPException(status_code=503, detail="SQL Agent Service not initialized")
    return sql_service

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def execute_query(
    request: QueryRequest,
    service: SQLAgentService = Depends(get_sql_service)
):
    start_time = time.time()
    try:
        logger.info(f"Processing query: {request.question}")
        result = await service.query(request.question, request.chart_type)
        processing_time = time.time() - start_time
        logger.info(f"Query completed in {processing_time:.2f}s")
        return result
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Query execution failed after {processing_time:.2f}s: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database/info", response_model=DatabaseInfo, tags=["Database"])
async def get_database_info(service: SQLAgentService = Depends(get_sql_service)):
    try:
        info = service.get_database_info()
        return DatabaseInfo(**info)
    except Exception as e:
        logger.error(f"Failed to get database info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database/tables", tags=["Database"])
async def get_database_tables(service: SQLAgentService = Depends(get_sql_service)):
    try:
        return {"tables": service.materialized_views}
    except Exception as e:
        logger.error(f"Failed to get database tables: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/insights/{job_id}", response_model=JobStatusResponse, tags=["Insights"])
async def get_insights_by_job_id(
    job_id: str,
    service: SQLAgentService = Depends(get_sql_service)
):
    try:
        job_status = service.get_job_status(job_id)
        
        if 'error' in job_status:
            raise HTTPException(status_code=404, detail=job_status['error'])
        
        return JobStatusResponse(**job_status)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/insights", tags=["Insights"])
async def get_all_jobs(service: SQLAgentService = Depends(get_sql_service)):
    try:
        # This would return all active jobs (for admin purposes)
        # For now, just return a message
        return {"message": "Use /insights/{job_id} to get specific job status"}
    except Exception as e:
        logger.error(f"Failed to get jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/insights/cleanup", tags=["Insights"])
async def cleanup_old_jobs(service: SQLAgentService = Depends(get_sql_service)):
    try:
        service.cleanup_old_jobs()
        return {"message": "Old jobs cleaned up successfully"}
    except Exception as e:
        logger.error(f"Failed to cleanup jobs: {str(e)}")
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
        "chart_types": {
            "auto": "Automatically detect the best chart type based on data and question",
            "bar": "Bar chart for comparisons and rankings",
            "line": "Line chart for time series and trends",
            "pie": "Pie chart for proportions and distributions",
            "table": "Table format for detailed data display",
            "none": "No chart - just return the raw data"
        },
        "workflow": {
            "step1": "POST /query with your question to get chart data and job_id",
            "step2": "GET /insights/{job_id} to check status and get insights when ready",
            "note": "Insights are generated in the background to avoid blocking the chart response"
        }
    }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 