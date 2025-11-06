#!/usr/bin/env python3
"""
Monitor and display form submission data in real-time.
"""

import json
import time
from pathlib import Path
from datetime import datetime

data_dir = Path(__file__).parent / "scraped-data"
shown_files = set()

print("🔍 Monitoring for form submissions...")
print("   When you submit a form, the data will be displayed here automatically")
print("   Press Ctrl+C to stop\n")

try:
    while True:
        # Find all patient-form-*.json files
        form_files = sorted(data_dir.glob("patient-form-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        for file in form_files:
            if file.name not in shown_files:
                shown_files.add(file.name)
                
                print("=" * 70)
                print("📄 NEW FORM SUBMISSION DETECTED!")
                print("=" * 70)
                print(f"File: {file.name}")
                print(f"Time: {datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    print("📊 Patient Data:")
                    print("-" * 70)
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    print()
                    print("=" * 70)
                    print()
                except Exception as e:
                    print(f"❌ Error reading file: {e}")
                    print()
        
        time.sleep(1)  # Check every second
        
except KeyboardInterrupt:
    print("\n\n👋 Monitoring stopped.")

