#!/usr/bin/env python3
"""Check and display form submission data."""

import json
import sys
from pathlib import Path
from datetime import datetime

data_dir = Path(__file__).parent / "scraped-data"

# Find the latest patient-form-*.json file
form_files = sorted(data_dir.glob("patient-form-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

if form_files:
    latest_file = form_files[0]
    print("=" * 60)
    print("📄 LATEST FORM SUBMISSION DATA")
    print("=" * 60)
    print(f"File: {latest_file.name}")
    print(f"Time: {datetime.fromtimestamp(latest_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("📊 Patient Data:")
        print("-" * 60)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print()
        print("=" * 60)
    except Exception as e:
        print(f"Error reading file: {e}")
else:
    print("⏳ No form submission files found yet.")
    print("   Waiting for you to submit a form...")
    print()
    print("   The script will automatically:")
    print("   1. Detect when you click 'Add Patient'")
    print("   2. Capture form data when you fill it")
    print("   3. Save data when you click 'Add' button")
    print("   4. Display it here automatically")

