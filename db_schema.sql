-- PostgreSQL schema for patient data
-- Run this script to create the database and table

-- Create database (uncomment if needed)
-- CREATE DATABASE solvhealth_patients;

-- Connect to the database before running the table creation
-- \c solvhealth_patients;

-- Create patients table
CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(255),
    solv_id VARCHAR(255),
    emr_id VARCHAR(255),
    location_id VARCHAR(255),
    location_name VARCHAR(255),
    legal_first_name VARCHAR(255),
    legal_last_name VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    mobile_phone VARCHAR(50),
    dob VARCHAR(50),
    date_of_birth DATE,
    reason_for_visit TEXT,
    sex_at_birth VARCHAR(50),
    gender VARCHAR(50),
    room VARCHAR(100),
    captured_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB,
    UNIQUE(patient_id, location_id, captured_at)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_patients_patient_id ON patients(patient_id);
CREATE INDEX IF NOT EXISTS idx_patients_emr_id ON patients(emr_id);
CREATE INDEX IF NOT EXISTS idx_patients_location_id ON patients(location_id);
CREATE INDEX IF NOT EXISTS idx_patients_captured_at ON patients(captured_at);
CREATE INDEX IF NOT EXISTS idx_patients_created_at ON patients(created_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_patients_updated_at ON patients;
CREATE TRIGGER update_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

