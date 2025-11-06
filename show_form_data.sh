#!/bin/bash
# Script to monitor and display form submission data

cd "$(dirname "$0")"

echo "🔍 Monitoring for form submissions..."
echo "   This will show data when forms are submitted"
echo ""

while true; do
    # Check for new patient-form-*.json files
    for file in scraped-data/patient-form-*.json; do
        if [ -f "$file" ]; then
            echo ""
            echo "═══════════════════════════════════════════════════════════════"
            echo "📄 NEW FORM SUBMISSION DETECTED!"
            echo "═══════════════════════════════════════════════════════════════"
            echo "File: $(basename "$file")"
            echo "Time: $(date)"
            echo ""
            echo "📊 Patient Data:"
            echo "───────────────────────────────────────────────────────────────"
            cat "$file" | python3 -m json.tool
            echo ""
            echo "═══════════════════════════════════════════════════════════════"
            echo ""
            
            # Move file to shown directory to avoid showing it again
            mkdir -p scraped-data/shown
            mv "$file" "scraped-data/shown/$(basename "$file")" 2>/dev/null
        fi
    done
    
    # Also check for patient-*.json files (with EMR ID)
    for file in scraped-data/patient-*.json; do
        if [ -f "$file" ] && [[ ! "$file" =~ patient-form- ]] && [[ ! "$file" =~ patients- ]]; then
            echo ""
            echo "═══════════════════════════════════════════════════════════════"
            echo "✅ PATIENT RECORD WITH EMR ID!"
            echo "═══════════════════════════════════════════════════════════════"
            echo "File: $(basename "$file")"
            echo "Time: $(date)"
            echo ""
            echo "📊 Patient Data with EMR ID:"
            echo "───────────────────────────────────────────────────────────────"
            cat "$file" | python3 -m json.tool
            echo ""
            echo "═══════════════════════════════════════════════════════════════"
            echo ""
            
            # Move file to shown directory
            mkdir -p scraped-data/shown
            mv "$file" "scraped-data/shown/$(basename "$file")" 2>/dev/null
        fi
    done
    
    sleep 2
done

