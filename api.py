#!/usr/bin/env python3
"""
FastAPI application to expose patient data via REST API.
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: Required packages not installed. Please run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

app = FastAPI(
    title="Patient Data API",
    description="API to access patient records from the database",
    version="1.0.0"
)


def get_db_connection():
    """Get PostgreSQL database connection from environment variables."""
    import getpass
    default_user = os.getenv('USER', os.getenv('USERNAME', getpass.getuser()))
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'solvhealth_patients'),
        'user': os.getenv('DB_USER', default_user),
        'password': os.getenv('DB_PASSWORD', '')
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection error: {str(e)}"
        )


def format_patient_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Format patient record for JSON response."""
    formatted = {}
    for key, value in record.items():
        # Convert datetime objects to ISO format strings
        if isinstance(value, datetime):
            formatted[key] = value.isoformat()
        # Convert date objects to ISO format strings
        elif hasattr(value, 'isoformat') and hasattr(value, 'year'):
            formatted[key] = value.isoformat()
        else:
            formatted[key] = value
    return formatted


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Patient Data API",
        "version": "1.0.0",
        "endpoints": {
            "GET /patient/{emr_id}": "Get patient record by EMR ID"
        }
    }


@app.get("/patient/{emr_id}")
async def get_patient_by_emr_id(emr_id: str):
    """
    Get a patient record by EMR ID.
    
    Returns the most recent patient record matching the given EMR ID.
    If multiple records exist, returns the one with the latest captured_at timestamp.
    
    Args:
        emr_id: The EMR ID of the patient to retrieve
        
    Returns:
        Patient record as JSON, or 404 if not found
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query for the most recent patient record with the given emr_id
        query = """
            SELECT 
                id, patient_id, solv_id, emr_id, location_id, location_name,
                legal_first_name, legal_last_name, first_name, last_name,
                mobile_phone, dob, date_of_birth, reason_for_visit,
                sex_at_birth, gender, room, captured_at, created_at, updated_at,
                raw_data
            FROM patients
            WHERE emr_id = %s
            ORDER BY captured_at DESC
            LIMIT 1;
        """
        
        cursor.execute(query, (emr_id,))
        record = cursor.fetchone()
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Patient with EMR ID '{emr_id}' not found"
            )
        
        # Convert to regular dict and format
        patient_data = dict(record)
        formatted_patient = format_patient_record(patient_data)
        
        return JSONResponse(content=formatted_patient)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('API_PORT', '8000'))
    host = os.getenv('API_HOST', '0.0.0.0')
    
    uvicorn.run(app, host=host, port=port)

