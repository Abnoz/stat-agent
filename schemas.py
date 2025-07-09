from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

class ChartDataPoint(BaseModel):
    label: str = Field(..., description="Label for the data point")
    value: Union[int, float] = Field(..., description="Numeric value")
    category: Optional[str] = Field(None, description="Category for grouping")

class TimeSeriesDataPoint(BaseModel):
    timestamp: datetime = Field(..., description="Timestamp for the data point")
    value: Union[int, float] = Field(..., description="Numeric value")
    metric: str = Field(..., description="Metric name")

class TableData(BaseModel):
    columns: List[str] = Field(..., description="Column names")
    rows: List[List[Any]] = Field(..., description="Row data")

class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question about the data")
    chart_type: Optional[str] = Field("auto", description="Preferred chart type: bar, line, pie, table, insight, auto")

class QueryResponse(BaseModel):
    success: bool = Field(..., description="Whether the query was successful")
    data: Optional[Union[List[ChartDataPoint], List[TimeSeriesDataPoint], TableData]] = Field(None, description="Chart-ready data")
    chart_type: str = Field(..., description="Recommended chart type")
    job_id: Optional[str] = Field(None, description="Background job ID for insights generation")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if any")

class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="Background job ID")
    status: str = Field(..., description="Job status: pending, processing, completed, failed")
    created_at: datetime = Field(..., description="When the job was created")
    completed_at: Optional[datetime] = Field(None, description="When the job was completed")
    question: str = Field(..., description="Original question")
    chart_type: str = Field(..., description="Chart type used")
    data_shape: str = Field(..., description="Data shape information")
    insights: Optional[str] = Field(None, description="AI-generated insights about the data")
    related_analysis: Optional[List[str]] = Field(None, description="Suggested follow-up questions for deeper analysis")
    error: Optional[str] = Field(None, description="Error message if job failed")

class DatabaseInfo(BaseModel):
    tables: List[str] = Field(..., description="Available table names")
    table_schemas: Dict[str, Dict[str, str]] = Field(..., description="Table schemas")

class ErrorResponse(BaseModel):
    success: bool = False
    error: str = Field(..., description="Error message")
    message: str = Field(..., description="User-friendly error message") 