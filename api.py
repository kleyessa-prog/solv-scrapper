#!/usr/bin/env python3
"""
FastAPI REST API for patient data.
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException, status
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError:
    print("Error: FastAPI is not installed. Please run: pip install -r requirements.txt")
    exit(1)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2-binary is not installed. Please run: pip install -r requirements.txt")
    exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


# Initialize FastAPI app
app = FastAPI(
    title="Patient Data API",
    description="REST API for accessing patient data from PostgreSQL database",
    version="1.0.0"
)


# Pydantic models for response
class PatientResponse(BaseModel):
    id: int
    patient_id: Optional[str]
    solv_id: Optional[str]
    emr_id: Optional[str]
    location_id: Optional[str]
    location_name: Optional[str]
    legal_first_name: Optional[str]
    legal_last_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    mobile_phone: Optional[str]
    dob: Optional[str]
    date_of_birth: Optional[str]
    reason_for_visit: Optional[str]
    sex_at_birth: Optional[str]
    gender: Optional[str]
    room: Optional[str]
    captured_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    raw_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


def get_db_connection():
    """Get PostgreSQL database connection from environment variables."""
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'solvhealth_patients'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', '')
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error: {str(e)}"
        )


def get_db_cursor(conn):
    """Get a database cursor that returns dict-like rows."""
    return conn.cursor(cursor_factory=RealDictCursor)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Patient Data API",
        "version": "1.0.0",
        "endpoints": {
            "GET /patient/{emr_id}": "Get patient record by EMR ID",
            "GET /docs": "API documentation (Swagger UI)",
            "GET /redoc": "Alternative API documentation (ReDoc)"
        }
    }


@app.get("/patient/{emr_id}", response_model=PatientResponse)
async def get_patient_by_emr_id(emr_id: str):
    """
    Get a patient record by EMR ID.
    
    Args:
        emr_id: The EMR (Electronic Medical Record) ID of the patient
    
    Returns:
        Patient record with all fields
    
    Raises:
        404: If patient with the given EMR ID is not found
        503: If database connection fails
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # Query patient by EMR ID
        query = """
            SELECT 
                id, patient_id, solv_id, emr_id, location_id, location_name,
                legal_first_name, legal_last_name, first_name, last_name,
                mobile_phone, dob, date_of_birth, reason_for_visit,
                sex_at_birth, gender, room, captured_at, created_at, updated_at,
                raw_data
            FROM patients
            WHERE emr_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        cursor.execute(query, (emr_id,))
        patient = cursor.fetchone()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with EMR ID '{emr_id}' not found"
            )
        
        # Convert date_of_birth to string if it exists
        patient_dict = dict(patient)
        if patient_dict.get('date_of_birth'):
            patient_dict['date_of_birth'] = patient_dict['date_of_birth'].isoformat()
        
        # Parse raw_data JSON if it exists
        if patient_dict.get('raw_data') and isinstance(patient_dict['raw_data'], str):
            try:
                import json
                patient_dict['raw_data'] = json.loads(patient_dict['raw_data'])
            except:
                pass
        
        return PatientResponse(**patient_dict)
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.get("/health")
async def health_check():
    """Health check endpoint to verify database connectivity."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8000
    port = int(os.getenv('API_PORT', 8000))
    host = os.getenv('API_HOST', '0.0.0.0')
    
    print(f"Starting Patient Data API on http://{host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")
    
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        reload=True  # Enable auto-reload during development
    )

