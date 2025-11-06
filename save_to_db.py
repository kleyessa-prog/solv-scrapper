#!/usr/bin/env python3
"""
Save JSON patient data to PostgreSQL database.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import psycopg2
    from psycopg2.extras import execute_values
    from psycopg2 import sql
except ImportError:
    print("Error: psycopg2-binary is not installed. Please run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


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
        print(f"Error connecting to database: {e}")
        print("\nPlease set the following environment variables:")
        print("  DB_HOST=localhost")
        print("  DB_PORT=5432")
        print("  DB_NAME=solvhealth_patients")
        print("  DB_USER=postgres")
        print("  DB_PASSWORD=your_password")
        print("\nOr create a .env file with these variables.")
        sys.exit(1)


def normalize_date(date_str: str) -> Optional[str]:
    """Normalize date string to YYYY-MM-DD format."""
    if not date_str or date_str.strip() == '':
        return None
    
    date_str = date_str.strip()
    
    # Try to parse various date formats
    formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%m-%d-%Y',
        '%d/%m/%Y',
        '%d-%m-%Y',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If all formats fail, return None
    return None


def normalize_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Normalize timestamp string to datetime object."""
    if not timestamp_str or timestamp_str.strip() == '':
        return None
    
    timestamp_str = timestamp_str.strip()
    
    # Try ISO format first
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError:
        pass
    
    # Try other common formats
    formats = [
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    
    return None


def normalize_patient_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize patient record from JSON to database format."""
    normalized = {
        'patient_id': record.get('patientId') or record.get('patient_id') or None,
        'solv_id': record.get('solvId') or record.get('solv_id') or None,
        'emr_id': record.get('emrId') or record.get('emr_id') or record.get('emr_id') or None,
        'location_id': record.get('locationId') or record.get('location_id') or None,
        'location_name': record.get('location_name') or record.get('locationName') or None,
        'legal_first_name': record.get('legalFirstName') or record.get('legal_first_name') or None,
        'legal_last_name': record.get('legalLastName') or record.get('legal_last_name') or None,
        'first_name': record.get('firstName') or record.get('first_name') or 
                     record.get('legalFirstName') or record.get('legal_first_name') or None,
        'last_name': record.get('lastName') or record.get('last_name') or 
                    record.get('legalLastName') or record.get('legal_last_name') or None,
        'mobile_phone': record.get('mobilePhone') or record.get('mobile_phone') or 
                       record.get('phone') or None,
        'dob': record.get('dob') or record.get('dateOfBirth') or record.get('date_of_birth') or None,
        'date_of_birth': None,  # Will be set from normalized dob
        'reason_for_visit': record.get('reasonForVisit') or record.get('reason_for_visit') or 
                           record.get('reason') or None,
        'sex_at_birth': record.get('sexAtBirth') or record.get('sex_at_birth') or None,
        'gender': record.get('gender') or record.get('sex') or 
                 record.get('sexAtBirth') or record.get('sex_at_birth') or None,
        'room': record.get('room') or record.get('roomNumber') or record.get('room_number') or None,
        'captured_at': normalize_timestamp(record.get('captured_at') or record.get('capturedAt')) or datetime.now(),
        'raw_data': json.dumps(record)
    }
    
    # Normalize date of birth
    if normalized['dob']:
        normalized['date_of_birth'] = normalize_date(normalized['dob'])
    
    # Clean up empty strings to None
    for key, value in normalized.items():
        if value == '':
            normalized[key] = None
    
    return normalized


def load_json_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load and parse JSON file, handling different structures."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Check for common keys that contain patient arrays
            for key in ['patients', 'data', 'items', 'results']:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # If it's a single patient object
            if 'patientId' in data or 'patient_id' in data or 'legalFirstName' in data:
                return [data]
        
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file {file_path}: {e}")
        return []
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []


def insert_patients(conn, patients: List[Dict[str, Any]], on_conflict: str = 'ignore'):
    """Insert patient records into database."""
    if not patients:
        return 0
    
    cursor = conn.cursor()
    
    insert_query = """
        INSERT INTO patients (
            patient_id, solv_id, emr_id, location_id, location_name,
            legal_first_name, legal_last_name, first_name, last_name,
            mobile_phone, dob, date_of_birth, reason_for_visit,
            sex_at_birth, gender, room, captured_at, raw_data
        ) VALUES %s
    """
    
    if on_conflict == 'ignore':
        insert_query += """
            ON CONFLICT (patient_id, location_id, captured_at) DO NOTHING
        """
    elif on_conflict == 'update':
        insert_query += """
            ON CONFLICT (patient_id, location_id, captured_at) DO UPDATE SET
                solv_id = EXCLUDED.solv_id,
                emr_id = EXCLUDED.emr_id,
                location_name = EXCLUDED.location_name,
                legal_first_name = EXCLUDED.legal_first_name,
                legal_last_name = EXCLUDED.legal_last_name,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                mobile_phone = EXCLUDED.mobile_phone,
                dob = EXCLUDED.dob,
                date_of_birth = EXCLUDED.date_of_birth,
                reason_for_visit = EXCLUDED.reason_for_visit,
                sex_at_birth = EXCLUDED.sex_at_birth,
                gender = EXCLUDED.gender,
                room = EXCLUDED.room,
                raw_data = EXCLUDED.raw_data,
                updated_at = CURRENT_TIMESTAMP
        """
    
    values = []
    for patient in patients:
        normalized = normalize_patient_record(patient)
        values.append((
            normalized['patient_id'],
            normalized['solv_id'],
            normalized['emr_id'],
            normalized['location_id'],
            normalized['location_name'],
            normalized['legal_first_name'],
            normalized['legal_last_name'],
            normalized['first_name'],
            normalized['last_name'],
            normalized['mobile_phone'],
            normalized['dob'],
            normalized['date_of_birth'],
            normalized['reason_for_visit'],
            normalized['sex_at_birth'],
            normalized['gender'],
            normalized['room'],
            normalized['captured_at'],
            normalized['raw_data']
        ))
    
    try:
        execute_values(cursor, insert_query, values)
        conn.commit()
        inserted_count = cursor.rowcount
        cursor.close()
        return inserted_count
    except psycopg2.Error as e:
        conn.rollback()
        cursor.close()
        print(f"Error inserting patients: {e}")
        raise


def save_json_to_db(json_file: Path, on_conflict: str = 'ignore'):
    """Save a single JSON file to database."""
    print(f"Processing {json_file.name}...")
    
    patients = load_json_file(json_file)
    if not patients:
        print(f"  ⚠️  No patient data found in {json_file.name}")
        return 0
    
    print(f"  📊 Found {len(patients)} patient record(s)")
    
    conn = get_db_connection()
    try:
        inserted = insert_patients(conn, patients, on_conflict=on_conflict)
        print(f"  ✅ Inserted {inserted} record(s) into database")
        return inserted
    finally:
        conn.close()


def save_all_json_files(directory: Path, on_conflict: str = 'ignore'):
    """Save all JSON files in a directory to database."""
    json_files = list(directory.glob('*.json'))
    
    if not json_files:
        print(f"No JSON files found in {directory}")
        return
    
    print(f"Found {len(json_files)} JSON file(s) to process\n")
    
    total_inserted = 0
    for json_file in sorted(json_files):
        try:
            inserted = save_json_to_db(json_file, on_conflict=on_conflict)
            total_inserted += inserted
        except Exception as e:
            print(f"  ❌ Error processing {json_file.name}: {e}")
    
    print(f"\n✨ Total records inserted: {total_inserted}")


def create_tables(conn):
    """Create database tables if they don't exist."""
    schema_file = Path(__file__).parent / 'db_schema.sql'
    
    if not schema_file.exists():
        print(f"Schema file not found: {schema_file}")
        return False
    
    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Remove CREATE DATABASE command if present (we're already connected)
        schema_sql = schema_sql.replace('CREATE DATABASE', '-- CREATE DATABASE')
        schema_sql = schema_sql.replace('\\c', '-- \\c')
        
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()
        cursor.close()
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"Error creating tables: {e}")
        conn.rollback()
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Save JSON patient data to PostgreSQL")
    parser.add_argument(
        '--file',
        type=str,
        help='Path to a specific JSON file to import'
    )
    parser.add_argument(
        '--directory',
        type=str,
        default='scraped-data',
        help='Directory containing JSON files to import (default: scraped-data)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Import all JSON files from the directory'
    )
    parser.add_argument(
        '--create-tables',
        action='store_true',
        help='Create database tables before importing'
    )
    parser.add_argument(
        '--on-conflict',
        choices=['ignore', 'update'],
        default='ignore',
        help='What to do on conflict: ignore (default) or update existing records'
    )
    
    args = parser.parse_args()
    
    # Create tables if requested
    if args.create_tables:
        print("Creating database tables...")
        conn = get_db_connection()
        try:
            create_tables(conn)
        finally:
            conn.close()
        print()
    
    # Process files
    if args.file:
        # Process single file
        json_file = Path(args.file)
        if not json_file.exists():
            print(f"Error: File not found: {json_file}")
            sys.exit(1)
        save_json_to_db(json_file, on_conflict=args.on_conflict)
    elif args.all:
        # Process all files in directory
        directory = Path(args.directory)
        if not directory.exists():
            print(f"Error: Directory not found: {directory}")
            sys.exit(1)
        save_all_json_files(directory, on_conflict=args.on_conflict)
    else:
        # Default: process patient_data.json
        json_file = Path('patient_data.json')
        if json_file.exists():
            save_json_to_db(json_file, on_conflict=args.on_conflict)
        else:
            print("Error: No file specified and patient_data.json not found.")
            print("Use --file to specify a file, --all to process all files, or --help for more options.")
            sys.exit(1)


if __name__ == '__main__':
    main()

