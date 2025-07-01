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
    chart_type: Optional[str] = Field("auto", description="Preferred chart type: bar, line, pie, table, auto")

class QueryResponse(BaseModel):
    success: bool = Field(..., description="Whether the query was successful")
    data: Optional[Union[List[ChartDataPoint], List[TimeSeriesDataPoint], TableData]] = Field(None, description="Chart-ready data")
    chart_type: str = Field(..., description="Recommended chart type")
    insights: Optional[str] = Field(None, description="AI-generated insights about the data and chart")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if any")

class DatabaseInfo(BaseModel):
    tables: List[str] = Field(..., description="Available table names")
    table_schemas: Dict[str, Dict[str, str]] = Field(..., description="Table schemas")

class ErrorResponse(BaseModel):
    success: bool = False
    error: str = Field(..., description="Error message")
    message: str = Field(..., description="User-friendly error message") 