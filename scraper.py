#!/usr/bin/env python3
"""
Solvhealth Scraper
A Playwright-based web scraper for extracting data from Solvhealth Management Portal.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from locations import (
    LOCATION_MAP,
    LOCATION_ID_TO_NAME,
    DEFAULT_LOCATION_ID,
    get_location_id,
    get_location_name,
    get_queue_url,
    list_all_locations,
)


def normalize_patient_data(patient_data, location_id=DEFAULT_LOCATION_ID, index=0):
    """
    Normalize patient data to the expected format.
    
    Args:
        patient_data: Dictionary or object with patient information
        location_id: Location ID to use (default: DEFAULT_LOCATION_ID)
        index: Index for generating IDs if not present
    
    Returns:
        Dictionary with normalized patient data
    """
    if not isinstance(patient_data, dict):
        return None
    
    # Extract or generate patientId
    # Check if this is an appointment/queue item that has patient nested
    if 'patient' in patient_data and isinstance(patient_data['patient'], dict):
        # Extract from nested patient object
        nested_patient = patient_data['patient']
        patient_id = (
            nested_patient.get('patientId') or 
            nested_patient.get('patient_id') or 
            nested_patient.get('id') or 
            nested_patient.get('_id') or
            patient_data.get('patientId') or
            patient_data.get('patient_id') or
            patient_data.get('id') or
            f"exp-{index + 1}"
        )
    else:
        patient_id = (
            patient_data.get('patientId') or 
            patient_data.get('patient_id') or 
            patient_data.get('id') or 
            patient_data.get('_id') or
            f"exp-{index + 1}"
        )
    
    # Extract or generate solvId
    solv_id = (
        patient_data.get('solvId') or 
        patient_data.get('solv_id') or 
        patient_data.get('solv') or
        patient_data.get('externalId') or
        patient_data.get('external_id') or
        f"solv-{index + 1}"
    )
    
    # Extract locationId
    location = (
        patient_data.get('locationId') or 
        patient_data.get('location_id') or 
        patient_data.get('location') or
        location_id
    )
    
    # Extract first name
    first_name = (
        patient_data.get('firstName') or 
        patient_data.get('first_name') or 
        patient_data.get('firstname') or
        patient_data.get('first') or
        patient_data.get('givenName') or
        patient_data.get('given_name') or
        (patient_data.get('name', '').split()[0] if patient_data.get('name') else '') or
        (patient_data.get('displayName', '').split()[0] if patient_data.get('displayName') else '') or
        (patient_data.get('fullName', '').split()[0] if patient_data.get('fullName') else '')
    )
    
    # Extract last name
    last_name = (
        patient_data.get('lastName') or 
        patient_data.get('last_name') or 
        patient_data.get('lastname') or
        patient_data.get('last') or
        patient_data.get('familyName') or
        patient_data.get('family_name') or
        (' '.join(patient_data.get('name', '').split()[1:]) if patient_data.get('name') else '') or
        (' '.join(patient_data.get('displayName', '').split()[1:]) if patient_data.get('displayName') else '') or
        (' '.join(patient_data.get('fullName', '').split()[1:]) if patient_data.get('fullName') else '')
    )
    
    # If name is in a nested object (like patient.name or user.name)
    if not first_name and not last_name:
        for key in ['patient', 'user', 'person', 'profile']:
            if key in patient_data and isinstance(patient_data[key], dict):
                nested = patient_data[key]
                first_name = nested.get('firstName') or nested.get('first_name') or nested.get('first') or (nested.get('name', '').split()[0] if nested.get('name') else '')
                last_name = nested.get('lastName') or nested.get('last_name') or nested.get('last') or (' '.join(nested.get('name', '').split()[1:]) if nested.get('name') else '')
                if first_name or last_name:
                    break
    
    # Also check for appointment/queue specific fields
    if not first_name and not last_name:
        # Sometimes appointment data has patient info at top level with different field names
        if 'first_name' in patient_data or 'last_name' in patient_data:
            first_name = patient_data.get('first_name') or patient_data.get('firstName') or ''
            last_name = patient_data.get('last_name') or patient_data.get('lastName') or ''
    
    # Extract DOB and normalize format
    # Check nested patient object first
    dob = ''
    if 'patient' in patient_data and isinstance(patient_data['patient'], dict):
        nested = patient_data['patient']
        dob = (
            nested.get('dob') or 
            nested.get('dateOfBirth') or 
            nested.get('date_of_birth') or
            nested.get('birthDate') or
            nested.get('birth_date') or
            ''
        )
    
    if not dob:
        dob = (
            patient_data.get('dob') or 
            patient_data.get('dateOfBirth') or 
            patient_data.get('date_of_birth') or
            patient_data.get('birthDate') or
            patient_data.get('birth_date') or
            ''
        )
    # Normalize date format to YYYY-MM-DD
    if dob:
        # Handle various date formats
        if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', dob):
            # Convert MM/DD/YYYY or MM-DD-YYYY to YYYY-MM-DD
            parts = re.split(r'[/-]', dob)
            if len(parts) == 3:
                if len(parts[2]) == 2:
                    parts[2] = '20' + parts[2]
                try:
                    dob = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                except:
                    pass
    
    # Extract gender (normalize to F/M)
    # Check nested patient object first
    gender = ''
    if 'patient' in patient_data and isinstance(patient_data['patient'], dict):
        nested = patient_data['patient']
        gender = nested.get('gender') or nested.get('sex') or ''
    
    if not gender:
        gender = (
            patient_data.get('gender') or 
            patient_data.get('sex') or
            ''
        )
    if gender:
        gender = str(gender).upper()
        if gender.startswith('F'):
            gender = 'F'
        elif gender.startswith('M'):
            gender = 'M'
        else:
            gender = ''
    
    # Extract room
    # Check nested patient object and appointment/queue fields
    room = ''
    if 'patient' in patient_data and isinstance(patient_data['patient'], dict):
        nested = patient_data['patient']
        room = nested.get('room') or nested.get('roomNumber') or nested.get('room_number') or ''
    
    if not room:
        # Also check appointment/queue specific fields
        room = (
            str(patient_data.get('room')) if patient_data.get('room') else
            str(patient_data.get('roomNumber')) if patient_data.get('roomNumber') else
            str(patient_data.get('room_number')) if patient_data.get('room_number') else
            str(patient_data.get('room_id')) if patient_data.get('room_id') else
            ''
        )
    
    return {
        "patientId": str(patient_id),
        "solvId": str(solv_id),
        "locationId": str(location),
        "firstName": str(first_name),
        "lastName": str(last_name),
        "dob": str(dob),
        "gender": str(gender),
        "room": str(room)
    }


async def auto_fill_patient_form_internal(page, location_id=DEFAULT_LOCATION_ID):
    """Internal function to auto-fill patient form using the same browser page."""
    try:
        sample_data = {
            "legalFirstName": "John",
            "legalLastName": "Doe",
            "mobilePhone": "(555) 123-4567",  # US phone number format
            "dob": "01/15/1990",  # MM/DD/YYYY format
            "reasonForVisit": "General checkup",
            "sexAtBirth": "Male"  # or "Female" depending on options
        }
        
        print("🔍 Looking for 'Add Patient' button...")
        await page.wait_for_timeout(2000)
        
        # Try multiple selectors for Add Patient button
        add_patient_selectors = [
            "button:has-text('Add Patient')",
            "button:has-text('Add patient')",
            "button:has-text('Add')",
            "[data-testid*='add']",
            "[class*='add-patient']",
        ]
        
        add_button_clicked = False
        for selector in add_patient_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=3000):
                    print(f"✅ Found 'Add Patient' button")
                    await button.click()
                    add_button_clicked = True
                    await page.wait_for_timeout(2000)
                    break
            except:
                continue
        
        if not add_button_clicked:
            print("⚠️  Could not find 'Add Patient' button")
            return
        
        # Wait for location selector modal (appears first)
        print("⏳ Waiting for location selector modal...")
        await page.wait_for_timeout(2000)
        
        # Extract location name from the location selector modal
        print("🔍 Extracting location name from location selector...")
        extracted_location_name = None
        location_field = None
        
        # Try to find location selector field and extract current value
        location_selectors = [
            "input[placeholder*='location']",
            "input[placeholder*='Location']",
            "input[name*='location']",
            "input[id*='location']",
            "input[type='search']",
            "input[aria-label*='location']",
            "input[aria-label*='Location']",
            "select[name*='location']",
            "select[id*='location']",
        ]
        
        # First, try to find the location field in a modal
        for selector in location_selectors:
            try:
                field = page.locator(selector).first
                # Check if it's in a modal/dialog
                modal_parent = field.locator("xpath=ancestor::*[@role='dialog' or contains(@class, 'modal')]")
                if await modal_parent.count() > 0 and await field.is_visible(timeout=2000):
                    print(f"   ✅ Found location selector: {selector}")
                    location_field = field
                    
                    # Extract the current location name/value
                    tag_name = await field.evaluate("el => el.tagName")
                    
                    if tag_name == "SELECT":
                        # For select dropdown, get the selected option text
                        selected_option = await field.evaluate("""
                            el => {
                                const selected = el.options[el.selectedIndex];
                                return selected ? selected.text : '';
                            }
                        """)
                        if selected_option:
                            extracted_location_name = selected_option.strip()
                            print(f"   📍 Found selected location: {extracted_location_name}")
                    else:
                        # For input field, get the value or placeholder
                        value = await field.input_value()
                        placeholder = await field.get_attribute("placeholder") or ""
                        
                        if value:
                            extracted_location_name = value.strip()
                            print(f"   📍 Found location value: {extracted_location_name}")
                        elif placeholder:
                            # Try to get from the displayed text near the input
                            try:
                                # Look for nearby text or labels
                                parent = await field.locator("xpath=..").first
                                parent_text = await parent.text_content()
                                if parent_text:
                                    # Try to extract location name from parent text
                                    for loc_name in LOCATION_MAP.keys():
                                        if loc_name in parent_text:
                                            extracted_location_name = loc_name
                                            print(f"   📍 Found location name from context: {extracted_location_name}")
                                            break
                            except:
                                pass
                    
                    # Also try to get location from visible text in the modal
                    if not extracted_location_name:
                        try:
                            modal = modal_parent.first
                            modal_text = await modal.text_content()
                            if modal_text:
                                # Try to match with our location names
                                for loc_name in LOCATION_MAP.keys():
                                    if loc_name in modal_text:
                                        extracted_location_name = loc_name
                                        print(f"   📍 Found location name from modal text: {extracted_location_name}")
                                        break
                        except:
                            pass
                    
                    break
            except:
                continue
        
        # If we found a location name, try to set it using our mapping
        location_set = False
        if extracted_location_name and location_field:
            # Try to match with our location mapping
            matched_location_id = get_location_id(extracted_location_name)
            
            if matched_location_id:
                print(f"   ✅ Matched location '{extracted_location_name}' to ID: {matched_location_id}")
                
                # Set the location in the field
                tag_name = await location_field.evaluate("el => el.tagName")
                
                if tag_name == "SELECT":
                    # For select, try to select by value or text
                    try:
                        await location_field.select_option(matched_location_id)
                        location_set = True
                        print(f"   ✅ Set location by ID: {matched_location_id}")
                    except:
                        try:
                            await location_field.select_option(label=extracted_location_name)
                            location_set = True
                            print(f"   ✅ Set location by name: {extracted_location_name}")
                        except:
                            # Try clicking option
                            options = await location_field.locator("option").all()
                            for opt in options:
                                opt_text = await opt.text_content()
                                opt_value = await opt.get_attribute("value")
                                if opt_text and (extracted_location_name in opt_text or opt_value == matched_location_id):
                                    await opt.click()
                                    location_set = True
                                    print(f"   ✅ Set location by clicking option")
                                    break
                else:
                    # For input field, try to fill with location name or search
                    try:
                        await location_field.fill(extracted_location_name)
                        await page.wait_for_timeout(1000)
                        
                        # Try to click the matching option from dropdown
                        option_selectors = [
                            f"li:has-text('{extracted_location_name}')",
                            f"div:has-text('{extracted_location_name}')",
                            f"[role='option']:has-text('{extracted_location_name}')",
                            f"button:has-text('{extracted_location_name}')",
                            f".option:has-text('{extracted_location_name}')",
                        ]
                        
                        for opt_selector in option_selectors:
                            try:
                                option = page.locator(opt_selector).first
                                if await option.is_visible(timeout=2000):
                                    await option.click()
                                    location_set = True
                                    print(f"   ✅ Selected location option: {extracted_location_name}")
                                    break
                            except:
                                continue
                        
                        if not location_set:
                            # Try pressing Enter
                            await location_field.press("Enter")
                            location_set = True
                            print(f"   ✅ Confirmed location by pressing Enter")
                    except:
                        pass
            else:
                print(f"   ⚠️  Location '{extracted_location_name}' not found in mapping, using as-is")
                # Still try to set it even if not in mapping
                try:
                    await location_field.fill(extracted_location_name)
                    await page.wait_for_timeout(1000)
                    await location_field.press("Enter")
                    location_set = True
                except:
                    pass
        
        if location_set:
            print(f"   ✅ Location set successfully")
            await page.wait_for_timeout(2000)
        else:
            print(f"   ⚠️  Could not set location, continuing...")
        
        # Wait for patient form modal to appear
        print("⏳ Waiting for patient form modal...")
        await page.wait_for_timeout(2000)
        
        # Fill form fields
        print("📝 Filling form fields...")
        
        # Legal First Name
        print("   Filling Legal First Name...")
        first_name_selectors = [
            "input[name*='legalFirst']",
            "input[id*='legalFirst']",
            "input[placeholder*='Legal First Name']",
            "input[placeholder*='First Name']",
            "label:has-text('Legal First Name') + * input",
            "label:has-text('Legal First Name') ~ input",
        ]
        for selector in first_name_selectors:
            try:
                field = page.locator(selector).first
                if await field.is_visible(timeout=1000):
                    await field.fill(sample_data["legalFirstName"])
                    print(f"   ✅ Filled Legal First Name: {sample_data['legalFirstName']}")
                    await page.wait_for_timeout(500)
                    break
            except:
                continue
                
        # Legal Last Name
        print("   Filling Legal Last Name...")
        last_name_selectors = [
            "input[name*='legalLast']",
            "input[id*='legalLast']",
            "input[placeholder*='Legal Last Name']",
            "input[placeholder*='Last Name']",
            "label:has-text('Legal Last Name') + * input",
            "label:has-text('Legal Last Name') ~ input",
        ]
        for selector in last_name_selectors:
            try:
                field = page.locator(selector).first
                if await field.is_visible(timeout=1000):
                    await field.fill(sample_data["legalLastName"])
                    print(f"   ✅ Filled Legal Last Name: {sample_data['legalLastName']}")
                    await page.wait_for_timeout(500)
                    break
            except:
                continue
        
        # Mobile Phone
        print("   Filling Mobile Phone...")
        phone_selectors = [
            "input[name*='mobile']",
            "input[name*='phone']",
            "input[id*='mobile']",
            "input[id*='phone']",
            "input[type='tel']",
            "input[placeholder*='phone']",
            "input[placeholder*='Phone']",
            "label:has-text('Mobile Phone') + * input",
            "label:has-text('Mobile Phone') ~ input",
        ]
        for selector in phone_selectors:
            try:
                field = page.locator(selector).first
                if await field.is_visible(timeout=1000):
                    await field.fill(sample_data["mobilePhone"])
                    print(f"   ✅ Filled Mobile Phone: {sample_data['mobilePhone']}")
                    await page.wait_for_timeout(500)
                    break
            except:
                continue
        
        # Date of Birth (MM/DD/YYYY format)
        print("   Filling Date of Birth...")
        dob_selectors = [
            "input[name*='dob']",
            "input[name*='birth']",
            "input[name*='dateOfBirth']",
            "input[id*='dob']",
            "input[id*='birth']",
            "input[type='date']",
            "input[placeholder*='MM/DD/YYYY']",
            "input[placeholder*='Date of Birth']",
            "label:has-text('Date of Birth') + * input",
            "label:has-text('Date of Birth') ~ input",
        ]
        for selector in dob_selectors:
            try:
                field = page.locator(selector).first
                if await field.is_visible(timeout=1000):
                    await field.fill(sample_data["dob"])
                    print(f"   ✅ Filled Date of Birth: {sample_data['dob']}")
                    await page.wait_for_timeout(500)
                    break
            except:
                continue
        
        # Reason for Visit
        print("   Filling Reason for Visit...")
        reason_selectors = [
            "input[name*='reason']",
            "input[name*='visit']",
            "input[id*='reason']",
            "input[id*='visit']",
            "textarea[name*='reason']",
            "textarea[name*='visit']",
            "input[placeholder*='reason for visit']",
            "input[placeholder*='Reason for Visit']",
            "label:has-text('Reason for Visit') + * input",
            "label:has-text('Reason for Visit') ~ textarea",
            "label:has-text('Reason for Visit') ~ input",
        ]
        for selector in reason_selectors:
            try:
                field = page.locator(selector).first
                if await field.is_visible(timeout=1000):
                    await field.fill(sample_data["reasonForVisit"])
                    print(f"   ✅ Filled Reason for Visit: {sample_data['reasonForVisit']}")
                    await page.wait_for_timeout(500)
                    break
            except:
                continue
        
        # Sex at Birth (dropdown selection)
        print("   Filling Sex at Birth (dropdown)...")
        sex_selectors = [
            "select[name*='sex']",
            "select[name*='gender']",
            "select[id*='sex']",
            "select[id*='gender']",
            "select[name*='birthSex']",
            "select[name*='sexAtBirth']",
            "select[name*='sexAtBirth']",
            "label:has-text('Sex at birth') + * select",
            "label:has-text('Sex at birth') ~ select",
            "label:has-text('Sex at Birth') + * select",
            "label:has-text('Sex at Birth') ~ select",
        ]
        for selector in sex_selectors:
            try:
                field = page.locator(selector).first
                # Make sure it's in the modal
                modal_parent = field.locator("xpath=ancestor::*[@role='dialog' or contains(@class, 'modal')]")
                if await modal_parent.count() > 0 and await field.is_visible(timeout=2000):
                    # It's a dropdown/select, so use select_option
                    # Try to select "Male" first
                    try:
                        await field.select_option("Male")
                        print(f"   ✅ Selected Sex at Birth: Male")
                        await page.wait_for_timeout(500)
                        break
                    except:
                        # Try "M"
                        try:
                            await field.select_option("M")
                            print(f"   ✅ Selected Sex at Birth: M")
                            await page.wait_for_timeout(500)
                            break
                        except:
                            # Try by text content in options
                            try:
                                options = await field.locator("option").all()
                                for opt in options:
                                    text = await opt.text_content()
                                    if text and ("male" in text.lower() or text.strip().upper() == "M"):
                                        value = await opt.get_attribute("value")
                                        if value:
                                            await field.select_option(value)
                                        else:
                                            await opt.click()
                                        print(f"   ✅ Selected Sex at Birth: {text.strip()}")
                                        await page.wait_for_timeout(500)
                                        break
                                break
                            except Exception as e:
                                print(f"   ⚠️  Error selecting sex at birth: {e}")
                                continue
            except:
                continue
        
        # Click Add/Submit button
        print("🔍 Clicking 'Add' button...")
        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Add')",
            "button:has-text('Submit')",
        ]
        
        for selector in submit_selectors:
            try:
                button = page.locator(selector).first
                # Make sure it's in modal
                modal_parent = button.locator("xpath=ancestor::*[@role='dialog' or contains(@class, 'modal')]")
                if await modal_parent.count() > 0 and await button.is_visible(timeout=2000):
                    await button.click()
                    print("✅ Clicked 'Add' button - form submitted!")
                    await page.wait_for_timeout(3000)
                    return
            except:
                continue
        
        print("⚠️  Could not find submit button")
        
    except Exception as e:
        print(f"⚠️  Error in auto-fill: {e}")
        import traceback
        traceback.print_exc()


async def scrape_solvhealth(queue_url=None, location_id=None, location_name=None, headless=False, slow_mo=500, auto_fill=False):
    """
    Scrape patient data from Solvhealth management portal queue.
    
    Args:
        queue_url: URL to the queue page to scrape (optional)
        location_id: Location ID string (optional, e.g., "AXjwbE")
        location_name: Location name string (optional, e.g., "Exer Urgent Care - Demo")
        headless: Run browser in headless mode (default: False)
        slow_mo: Slow down operations by milliseconds (default: 500)
        auto_fill: Automatically fill and submit a patient form (default: False)
    """
    print("🚀 Starting Solvhealth patient scraper...")
    print(f"   Mode: {'Headless' if headless else 'Visible'}")
    
    # Determine queue URL
    if queue_url is None:
        if location_id:
            queue_url = get_queue_url(location_id=location_id)
        elif location_name:
            queue_url = get_queue_url(location_name=location_name)
        else:
            queue_url = get_queue_url()  # Uses default location
    
    # Extract location_id from queue_url if not provided
    if not location_id:
        if location_name:
            location_id = get_location_id(location_name)
        else:
            # Try to extract from URL
            try:
                if 'location_ids=' in queue_url:
                    location_id = queue_url.split('location_ids=')[1].split('&')[0]
            except:
                pass
    
    if not location_id:
        location_id = DEFAULT_LOCATION_ID
    
    location_display = get_location_name(location_id) or location_id
    print(f"   Location: {location_display} ({location_id})")
    
    # Create output directories
    base_dir = Path(__file__).parent
    screenshots_dir = base_dir / "screenshots"
    data_dir = base_dir / "scraped-data"
    screenshots_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)
    
    async with async_playwright() as p:
        # Use persistent browser context to save login session
        # This allows you to login once manually and reuse the session
        user_data_dir = base_dir / ".browser-data"
        user_data_dir.mkdir(exist_ok=True)
        
        # Try to use Chrome, fallback to Chromium if Chrome is not available
        browser_launcher = None
        try:
            # Try Chrome first (if installed)
            browser_launcher = p.chrome
            print("✅ Using Chrome browser")
        except Exception:
            # Fallback to Chromium
            browser_launcher = p.chromium
            print("✅ Using Chromium browser")
        
        # Launch with persistent context (saves cookies and session)
        # Use screen-appropriate viewport size to prevent cropping
        # Using 1920x1080 for standard full-screen display
        context = await browser_launcher.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            slow_mo=slow_mo,
            viewport=None,  # Use full browser window size (no viewport restriction)
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        print("💡 Tip: You can login manually in the browser window")
        print("   Your login session will be saved and reused in future runs")
        
        # Get the first page or create a new one
        pages = context.pages
        if pages:
            page = pages[0]
        else:
            page = await context.new_page()
        
        # Store intercepted API responses and requests for patient data
        api_responses = []
        api_requests = []  # Track requests to detect form submissions
        
        # Intercept network requests to detect form submissions
        async def handle_request(request):
            """Capture API requests that might indicate form submissions."""
            try:
                url_lower = request.url.lower() if request.url else ''
                if url_lower and request.method in ['POST', 'PUT']:
                    if 'patient' in url_lower or 'create' in url_lower or 'add' in url_lower:
                        try:
                            # Try to get post data
                            post_data = None
                            try:
                                post_data = request.post_data
                            except:
                                # Try to get from request body
                                try:
                                    body = request.post_data_json if hasattr(request, 'post_data_json') else None
                                    if body:
                                        post_data = body
                                except:
                                    pass
                            
                            api_requests.append({
                                'url': request.url,
                                'method': request.method,
                                'data': post_data,
                                'time': datetime.now()
                            })
                            print(f"📤 Detected {request.method} request to: {request.url}")
                        except Exception as e:
                            pass
            except Exception:
                pass
        
        # Intercept network responses to capture patient data from API calls
        async def handle_response(response):
            """Capture API responses that might contain patient data."""
            try:
                url_lower = response.url.lower() if response.url else ''
                # Skip auth/token endpoints
                if 'token' in url_lower or 'auth' in url_lower or 'login' in url_lower:
                    return
                
                if url_lower and ('queue' in url_lower or 'patient' in url_lower or 'api' in url_lower or 'appointment' in url_lower):
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        try:
                            data = await response.json()
                            # Capture any response that might contain patient data
                            # Check for various structures
                            has_patient_data = False
                            if isinstance(data, dict):
                                # Skip token responses
                                if 'access_token' in data or 'token' in data:
                                    return
                                # Check for direct patient arrays
                                if 'patients' in data or 'queue' in data or 'data' in data:
                                    has_patient_data = True
                                # Check for nested structures
                                elif any('patient' in str(k).lower() for k in data.keys()):
                                    has_patient_data = True
                                # Check if values are arrays that might contain patient objects
                                elif any(isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) for v in data.values()):
                                    has_patient_data = True
                            elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                                has_patient_data = True
                            
                            if has_patient_data:
                                api_responses.append({
                                    'url': response.url,
                                    'data': data
                                })
                        except Exception:
                            pass
            except Exception:
                pass
                
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        # Set up navigation detection
        navigation_detected = False
        navigation_event = asyncio.Event()
        
        def on_navigation(frame):
            """Detect when user navigates to queue page."""
            nonlocal navigation_detected
            try:
                url = frame.url if hasattr(frame, 'url') else page.url
                if "/queue" in url or "queue" in url.lower():
                    if not navigation_detected:
                        navigation_detected = True
                        navigation_event.set()
                        print(f"✅ Queue page navigation detected: {url}")
            except Exception:
                pass
        
        # Listen for navigation events
        page.on("framenavigated", on_navigation)
        
        try:
            # Navigate to base URL first
            base_url = "https://manage.solvhealth.com/"
            print(f"📡 Opening browser and navigating to base URL: {base_url}")
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2000)
                print(f"✅ Base URL loaded: {page.url}")
            except Exception as e:
                print(f"⚠️  Navigation to base URL issue: {e}")
            
            # Check if already on queue page
            try:
                current_url = page.url
                if "/queue" in current_url or "queue" in current_url.lower():
                    navigation_detected = True
                    navigation_event.set()
                    print(f"✅ Already on queue page: {current_url}")
            except Exception:
                pass
                
            # Wait for user to navigate to the queue page (or navigate directly if auto-fill is enabled)
            if auto_fill and not navigation_detected:
                # If auto-fill is enabled, navigate directly to queue page
                print(f"🤖 Auto-fill enabled - navigating directly to queue page: {queue_url}")
                try:
                    await page.goto(queue_url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(2000)
                    navigation_detected = True
                    navigation_event.set()
                    print(f"✅ Navigated to queue page: {page.url}")
                except Exception as e:
                    print(f"⚠️  Error navigating to queue page: {e}")
            
            if not navigation_detected:
                print("⏳ Waiting for you to navigate to the queue page...")
                print("   Navigate to a page containing '/queue' in the browser window")
                print("   Script will start automatically when queue page is detected")
                
                # Wait for navigation event (with timeout)
                try:
                    await asyncio.wait_for(navigation_event.wait(), timeout=300.0)  # 5 minutes max wait
                except asyncio.TimeoutError:
                    print("⚠️  Navigation timeout - starting monitoring anyway...")
            
            # Wait for page to fully load
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
                await page.wait_for_timeout(3000)  # Give extra time for dynamic content
            except Exception:
                print("⚠️  Page load timeout, continuing anyway...")
            
            # Check if page is still open
            if page.is_closed():
                raise Exception("Page was closed unexpectedly")
            
            print(f"✅ Ready! Current URL: {page.url}")
            
            # Extract location_id from current URL first (use provided or extract from URL)
            if not location_id:
                try:
                    current_url = page.url
                    if 'location_ids=' in current_url:
                        location_id = current_url.split('location_ids=')[1].split('&')[0]
                    elif queue_url and 'location_ids=' in queue_url:
                        location_id = queue_url.split('location_ids=')[1].split('&')[0]
                except:
                    pass
            
            if not location_id:
                location_id = DEFAULT_LOCATION_ID
            
            # Auto-fill form if requested
            if auto_fill:
                print("🤖 Auto-fill mode enabled - will automatically fill and submit form...")
                await auto_fill_patient_form_internal(page, location_id=location_id)
            
            print("👀 Starting to monitor for patient form submissions...")
            print("   Waiting for 'Add Patient' button clicks and form submissions...")
            
            # Track submitted patient forms
            submitted_patients = []  # List of patient data from form submissions
            monitoring_patients = {}  # {submission_id: {patient_data, submission_time}}
            processed_patient_ids = set()
            
            # Wait times for EMR ID
            emr_wait_min = 60  # Minimum wait time for EMR ID (60 seconds)
            emr_wait_max = 90  # Maximum wait time for EMR ID (90 seconds)
            check_interval = 2  # Check every 2 seconds
            
            def extract_patient_id(patient_data):
                """Extract patient ID from patient data object."""
                if isinstance(patient_data, dict):
                    return (
                        patient_data.get('patientId') or 
                        patient_data.get('patient_id') or 
                        patient_data.get('id') or
                        patient_data.get('_id') or
                        ''
                    )
                return ''
            
            def extract_emr_id(patient_data):
                """Extract EMR ID from patient data object."""
                if not isinstance(patient_data, dict):
                    return ''
                
                emr_id = (
                    patient_data.get('emrId') or 
                    patient_data.get('emr_id') or 
                    patient_data.get('emr') or
                    patient_data.get('externalId') or
                    patient_data.get('external_id') or
                    ''
                )
                
                # Also check nested patient object
                if not emr_id and 'patient' in patient_data and isinstance(patient_data['patient'], dict):
                    nested = patient_data['patient']
                    emr_id = (
                        nested.get('emrId') or 
                        nested.get('emr_id') or 
                        nested.get('emr') or
                        nested.get('externalId') or
                        nested.get('external_id') or
                        ''
                    )
                
                return emr_id
            
            def save_to_patient_data_json(form_data, location_id, location_name, emr_id=''):
                """Save patient data to patient_data.json file in the expected format."""
                try:
                    script_dir = Path(__file__).parent.absolute()
                    output_path = script_dir / "patient_data.json"
                    
                    # Prepare data in the expected format
                    patient_entry = {
                        'location_id': location_id,
                        'location_name': location_name,
                        'legalFirstName': form_data.get('legalFirstName', '') or form_data.get('firstName', ''),
                        'legalLastName': form_data.get('legalLastName', '') or form_data.get('lastName', ''),
                        'mobilePhone': form_data.get('mobilePhone', '') or form_data.get('phone', ''),
                        'dob': form_data.get('dob', '') or form_data.get('dateOfBirth', ''),
                        'reasonForVisit': form_data.get('reasonForVisit', '') or form_data.get('reason', ''),
                        'sexAtBirth': form_data.get('sexAtBirth', '') or form_data.get('gender', '') or form_data.get('sex', ''),
                        'emr_id': emr_id,
                        'captured_at': datetime.now().isoformat()
                    }
                    
                    # Load existing data if file exists
                    if output_path.exists():
                        try:
                            with open(output_path, 'r', encoding='utf-8') as f:
                                existing_data = json.load(f)
                            if isinstance(existing_data, list):
                                existing_data.append(patient_entry)
                                data_to_save = existing_data
                            else:
                                data_to_save = [existing_data, patient_entry]
                        except json.JSONDecodeError as e:
                            print(f"   ⚠️  JSON decode error, starting fresh: {e}")
                            data_to_save = [patient_entry]
                    else:
                        data_to_save = [patient_entry]
                    
                    # Save to file
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                    
                    print(f"✅ Saved to patient_data.json: {output_path}")
                    print(f"   📊 Total entries: {len(data_to_save)}")
                    return True
                except Exception as e:
                    print(f"❌ Error saving to patient_data.json: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
            
            def update_emr_id_in_patient_data_json(form_data, emr_id, location_id):
                """Update EMR ID in existing patient_data.json entry."""
                try:
                    script_dir = Path(__file__).parent.absolute()
                    output_path = script_dir / "patient_data.json"
                    
                    if not output_path.exists():
                        return False
                    
                    # Load existing data
                    with open(output_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]
                    
                    # Find matching entry (by name and recent timestamp)
                    form_first = (form_data.get('legalFirstName', '') or form_data.get('firstName', '')).strip()
                    form_last = (form_data.get('legalLastName', '') or form_data.get('lastName', '')).strip()
                    
                    updated = False
                    # Find the most recent entry without EMR ID that matches
                    for entry in reversed(existing_data):
                        if entry.get('emr_id'):
                            continue  # Skip entries that already have EMR ID
                        
                        entry_first = (entry.get('legalFirstName', '')).strip()
                        entry_last = (entry.get('legalLastName', '')).strip()
                        
                        # Match by name (case insensitive)
                        if form_first and form_last:
                            if (entry_first.lower() == form_first.lower() and 
                                entry_last.lower() == form_last.lower()):
                                entry['emr_id'] = str(emr_id)
                                updated = True
                                break
                        elif form_first:
                            if entry_first.lower() == form_first.lower():
                                entry['emr_id'] = str(emr_id)
                                updated = True
                                break
                        elif form_last:
                            if entry_last.lower() == form_last.lower():
                                entry['emr_id'] = str(emr_id)
                                updated = True
                                break
                    
                    if updated:
                        # Save updated data
                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(existing_data, f, indent=2, ensure_ascii=False)
                        print(f"✅ Updated EMR ID in patient_data.json: {emr_id}")
                        return True
                    
                    return False
                except Exception as e:
                    print(f"❌ Error updating EMR ID in patient_data.json: {e}")
                    return False
            
            def save_patient_record(patient_data, patient_id, location_id):
                """Save a patient record ONLY if it has EMR ID."""
                emr_id = extract_emr_id(patient_data)
                if not emr_id:
                    # Don't save if no EMR ID
                    return False
                
                normalized = normalize_patient_data(patient_data, location_id, len(processed_patient_ids))
                if normalized:
                    normalized['emrId'] = str(emr_id)
                    
                    timestamp = int(datetime.now().timestamp() * 1000)
                    patient_file = data_dir / f"patient-{patient_id}-{timestamp}.json"
                    patient_record = {"patients": [normalized]}
                    
                    with open(patient_file, "w", encoding="utf-8") as f:
                        json.dump(patient_record, f, indent=2, ensure_ascii=False)
                    
                    print(f"💾 Patient record saved with EMR ID: {patient_file}")
                    
                    # Update EMR ID in patient_data.json (try to update existing entry first)
                    # Convert normalized data back to form data format
                    form_data_for_json = {
                        'legalFirstName': normalized.get('firstName', ''),
                        'legalLastName': normalized.get('lastName', ''),
                        'mobilePhone': patient_data.get('mobilePhone', '') or patient_data.get('phone', ''),
                        'dob': normalized.get('dob', ''),
                        'reasonForVisit': patient_data.get('reasonForVisit', '') or patient_data.get('reason', ''),
                        'sexAtBirth': normalized.get('gender', '') or patient_data.get('sexAtBirth', '')
                    }
                    
                    # Try to update existing entry, if not found, create new one
                    location_name = get_location_name(location_id)
                    if not update_emr_id_in_patient_data_json(form_data_for_json, emr_id, location_id):
                        # No existing entry found, create new one
                        save_to_patient_data_json(form_data_for_json, location_id, location_name, str(emr_id))
                    
                    return True
                return False
            
            def extract_form_data(modal_element):
                """Extract patient data from modal form."""
                try:
                    form_data = {}
                    # Try to extract form fields
                    inputs = modal_element.query_selector_all('input, select, textarea')
                    for input_elem in inputs:
                        name = input_elem.get_attribute('name') or input_elem.get_attribute('id') or ''
                        value = input_elem.get_attribute('value') or ''
                        if name:
                            # Normalize field names
                            if 'first' in name.lower():
                                form_data['firstName'] = value
                            elif 'last' in name.lower():
                                form_data['lastName'] = value
                            elif 'dob' in name.lower() or 'birth' in name.lower() or 'date' in name.lower():
                                form_data['dob'] = value
                            elif 'gender' in name.lower() or 'sex' in name.lower():
                                form_data['gender'] = value
                            elif 'room' in name.lower():
                                form_data['room'] = value
                            else:
                                form_data[name] = value
                    return form_data
                except Exception as e:
                    print(f"⚠️  Error extracting form data: {e}")
                    return {}
            
            # Set up monitoring for "Add Patient" button clicks and modal form submissions
            modal_visible = False
            form_submission_tracked = set()  # Track submissions to avoid duplicates
            
            async def monitor_add_patient_flow():
                """Monitor for add patient button clicks and form submissions."""
                nonlocal modal_visible
                
                # Set up multiple listeners to catch form submissions
                await page.evaluate("""
                    () => {
                        // Clear previous state
                        window._formSubmitData = null;
                        window._formSubmitTime = null;
                        window._lastFormData = null;
                        
                        // Remove existing listeners if any
                        if (window._formSubmitClickListener) {
                            document.removeEventListener('click', window._formSubmitClickListener, true);
                        }
                        if (window._formSubmitFormListener) {
                            document.removeEventListener('submit', window._formSubmitFormListener, true);
                        }
                        
                        // Function to capture form data immediately
                        function captureFormData() {
                            const modal = document.querySelector('[role="dialog"]:not([style*="display: none"]), .modal:not([style*="display: none"]), [class*="modal"]:not([style*="display: none"]), [class*="Modal"]:not([style*="display: none"])');
                            if (!modal) return null;
                            
                            const formData = {};
                            const inputs = modal.querySelectorAll('input, select, textarea');
                            
                            inputs.forEach(input => {
                                const name = input.name || input.id || input.getAttribute('data-field') || input.getAttribute('data-name') || '';
                                const placeholder = input.placeholder || '';
                                let value = '';
                                
                                if (input.type === 'checkbox' || input.type === 'radio') {
                                    value = input.checked;
                                } else if (input.tagName === 'SELECT') {
                                    const selectedOption = input.options[input.selectedIndex];
                                    value = selectedOption ? selectedOption.text : input.value;
                                } else {
                                    value = input.value || input.textContent || '';
                                }
                                
                                if (value || name) {
                                    const normalizedName = name.toLowerCase().replace(/[^a-z0-9]/g, '');
                                    const placeholderLower = placeholder.toLowerCase();
                                    
                                    // Map to known fields
                                    if (normalizedName.includes('legalfirst') || placeholderLower.includes('legal first name')) {
                                        formData['legalFirstName'] = value;
                                    } else if (normalizedName.includes('legallast') || placeholderLower.includes('legal last name')) {
                                        formData['legalLastName'] = value;
                                    } else if (normalizedName.includes('mobile') || normalizedName.includes('phone') || placeholderLower.includes('mobile phone')) {
                                        formData['mobilePhone'] = value;
                                    } else if (normalizedName.includes('dob') || normalizedName.includes('dateofbirth') || placeholderLower.includes('date of birth')) {
                                        formData['dob'] = value;
                                    } else if (normalizedName.includes('reason') || normalizedName.includes('visit') || placeholderLower.includes('reason for visit')) {
                                        formData['reasonForVisit'] = value;
                                    } else if (normalizedName.includes('sexatbirth') || normalizedName.includes('sex_at_birth') || placeholderLower.includes('sex at birth')) {
                                        formData['sexAtBirth'] = value;
                                    } else if (normalizedName.includes('first') || normalizedName.includes('fname')) {
                                        formData['firstName'] = value;
                                        if (!formData['legalFirstName']) formData['legalFirstName'] = value;
                                    } else if (normalizedName.includes('last') || normalizedName.includes('lname')) {
                                        formData['lastName'] = value;
                                        if (!formData['legalLastName']) formData['legalLastName'] = value;
                                    } else {
                                        formData[name || input.id || `field_${inputs.length}`] = value;
                                    }
                                }
                            });
                            
                            return formData;
                        }
                        
                        // Click listener - capture data immediately when Add button is clicked
                        window._formSubmitClickListener = function(event) {
                            const target = event.target;
                            const button = target.closest('button');
                            
                            if (button) {
                                const buttonText = (button.textContent || button.innerText || '').trim().toLowerCase();
                                const buttonType = button.type || '';
                                const inModal = button.closest('[role="dialog"], .modal, [class*="modal"], [class*="Modal"], [class*="dialog"], [class*="Dialog"]');
                                
                                // Check if this is an "Add" or "Submit" button in a modal
                                if ((buttonText.includes('add') || buttonText === 'submit' || buttonType === 'submit') && inModal) {
                                    // Immediately capture form data
                                    const formData = captureFormData();
                                    if (formData && Object.keys(formData).length > 0) {
                                        window._formSubmitData = formData;
                                        window._formSubmitTime = Date.now();
                                        button.setAttribute('data-form-submitted', 'true');
                                        console.log('✅ Form submission detected! Data captured:', formData);
                                    }
                                }
                            }
                        };
                        
                        // Form submit listener (for form elements)
                        window._formSubmitFormListener = function(event) {
                            const form = event.target;
                            const modal = form.closest('[role="dialog"], .modal, [class*="modal"], [class*="Modal"]');
                            if (modal) {
                                const formData = captureFormData();
                                if (formData && Object.keys(formData).length > 0) {
                                    window._formSubmitData = formData;
                                    window._formSubmitTime = Date.now();
                                    console.log('✅ Form submit event detected! Data captured:', formData);
                                }
                            }
                        };
                        
                        document.addEventListener('click', window._formSubmitClickListener, true);
                        document.addEventListener('submit', window._formSubmitFormListener, true);
                        
                        // Also periodically capture form data while modal is open
                        setInterval(() => {
                            const modal = document.querySelector('[role="dialog"]:not([style*="display: none"]), .modal:not([style*="display: none"])');
                            if (modal) {
                                const formData = captureFormData();
                                if (formData && Object.keys(formData).length > 0) {
                                    window._lastFormData = formData;
                                }
                            }
                        }, 1000);
                    }
                """)
                
                while True:
                    try:
                        # Check if modal is visible (user clicked "Add Patient")
                        modal_selectors = [
                            "[role='dialog']:visible",
                            ".modal:visible",
                            "[class*='modal']:not([style*='display: none'])",
                            "[class*='Modal']:not([style*='display: none'])",
                            "[class*='dialog']:not([style*='display: none'])",
                            "[class*='Dialog']:not([style*='display: none'])"
                        ]
                        
                        modal_found = False
                        for selector in modal_selectors:
                            try:
                                modal = page.locator(selector).first
                                if await modal.is_visible():
                                    modal_found = True
                                    if not modal_visible:
                                        print("✅ Modal detected! User clicked 'Add Patient'")
                                        modal_visible = True
                                        
                                        # Analyze modal structure on first detection
                                        print("\n🔍 Analyzing modal structure...")
                                        modal_structure = await page.evaluate("""
                    () => {
                                                const modal = document.querySelector('[role="dialog"]:visible, .modal:visible, [class*="modal"]:not([style*="display: none"])');
                                                if (!modal) return null;
                                                
                                                const structure = {
                                                    modalTag: modal.tagName,
                                                    modalClasses: modal.className || '',
                                                    modalId: modal.id || '',
                                                    fields: []
                                                };
                                                
                                                const inputs = modal.querySelectorAll('input, select, textarea');
                                                inputs.forEach((input, idx) => {
                                                    let label = null;
                                                    if (input.id) {
                                                        label = document.querySelector(`label[for="${input.id}"]`);
                                                    }
                                                    if (!label) {
                                                        label = input.closest('label') || input.parentElement?.querySelector('label');
                                                    }
                                                    
                                                    const fieldInfo = {
                                                        index: idx,
                                                        tag: input.tagName,
                                type: input.type || input.tagName.toLowerCase(),
                                                        name: input.name || '',
                                                        id: input.id || '',
                                                        placeholder: input.placeholder || '',
                                                        labelText: label ? label.textContent?.trim() : '',
                                required: input.required || false
                                                    };
                                                    
                                                    if (input.tagName === 'SELECT') {
                                                        fieldInfo.options = [];
                                                        Array.from(input.options).slice(0, 5).forEach(opt => {
                                                            fieldInfo.options.push({
                                                                value: opt.value,
                                                                text: opt.text
                                                            });
                                                        });
                                                    }
                                                    
                                                    structure.fields.push(fieldInfo);
                                                });
                                                
                                                return structure;
                                            }
                                        """)
                                        
                                        if modal_structure:
                                            print(f"   📋 Modal: {modal_structure.get('modalTag', 'N/A')}")
                                            print(f"   📋 Fields found: {len(modal_structure.get('fields', []))}")
                                            print("\n   📝 Form Fields:")
                                            for i, field in enumerate(modal_structure.get('fields', []), 1):
                                                print(f"      {i}. {field.get('tag', 'N/A')} - {field.get('type', 'N/A')}")
                                                print(f"         Name: {field.get('name', 'N/A') or 'N/A'}")
                                                print(f"         ID: {field.get('id', 'N/A') or 'N/A'}")
                                                print(f"         Placeholder: {field.get('placeholder', 'N/A') or 'N/A'}")
                                                print(f"         Label: {field.get('labelText', 'N/A') or 'N/A'}")
                                                if field.get('options'):
                                                    print(f"         Options: {len(field.get('options', []))} available")
                                            print("")
                                    
                                    # Extract form data from the modal
                                    form_data = await page.evaluate("""
                    () => {
                                            const modal = document.querySelector('[role="dialog"]:visible, .modal:visible, [class*="modal"]:not([style*="display: none"])');
                                            if (!modal) return null;
                                            
                                            const formData = {};
                                            
                                            // Try to get all form inputs
                                            const inputs = modal.querySelectorAll('input, select, textarea');
                                            inputs.forEach(input => {
                                                const name = input.name || input.id || input.getAttribute('data-field') || input.getAttribute('data-name') || '';
                                                const placeholder = input.placeholder || '';
                                                let value = '';
                                                
                                                // Handle different input types
                                                if (input.type === 'checkbox' || input.type === 'radio') {
                                                    value = input.checked;
                                                } else if (input.tagName === 'SELECT') {
                                                    const selectedOption = input.options[input.selectedIndex];
                                                    value = selectedOption ? selectedOption.text : input.value;
                                                } else if (input.type === 'date' || input.type === 'datetime-local') {
                                                    value = input.value || input.getAttribute('value') || '';
                                                } else {
                                                    value = input.value || input.textContent || '';
                                                }
                                                
                                                // Skip if value is empty or just placeholder text
                                                if (!value || value === placeholder) {
                                                    return;
                                                }
                                                
                                                if (name || input.id) {
                                                    // Normalize field names - handle specific field names
                                                    const normalizedName = name.toLowerCase();
                                                    const placeholderLower = placeholder.toLowerCase();
                                                    
                                                    // Legal First Name
                                                    if (normalizedName.includes('legalfirst') || normalizedName.includes('legal_first') || 
                                                        placeholderLower.includes('legal first name') || normalizedName.includes('firstname')) {
                                                        formData['legalFirstName'] = value;
                                                        formData['firstName'] = value; // Also save as firstName for compatibility
                                                    }
                                                    // Legal Last Name
                                                    else if (normalizedName.includes('legallast') || normalizedName.includes('legal_last') || 
                                                             placeholderLower.includes('legal last name') || normalizedName.includes('lastname')) {
                                                        formData['legalLastName'] = value;
                                                        formData['lastName'] = value; // Also save as lastName for compatibility
                                                    }
                                                    // Mobile Phone
                                                    else if (normalizedName.includes('mobile') || normalizedName.includes('phone') || 
                                                             placeholderLower.includes('mobile phone') || placeholderLower.includes('phone number')) {
                                                        formData['mobilePhone'] = value;
                                                        formData['phone'] = value;
                                                    }
                                                    // Date of Birth
                                                    else if (normalizedName.includes('dob') || normalizedName.includes('dateofbirth') || 
                                                             normalizedName.includes('birth') || placeholderLower.includes('date of birth') ||
                                                             placeholderLower.includes('mm/dd/yyyy')) {
                                                        formData['dob'] = value;
                                                        formData['dateOfBirth'] = value;
                                                    }
                                                    // Reason for Visit
                                                    else if (normalizedName.includes('reason') || normalizedName.includes('visit') ||
                                                             placeholderLower.includes('reason for visit')) {
                                                        formData['reasonForVisit'] = value;
                                                        formData['reason'] = value;
                                                    }
                                                    // Sex at Birth
                                                    else if (normalizedName.includes('sexatbirth') || normalizedName.includes('sex_at_birth') ||
                                                             normalizedName.includes('birthsex') || placeholderLower.includes('sex at birth')) {
                                                        formData['sexAtBirth'] = value;
                                                        formData['gender'] = value;
                                                        formData['sex'] = value;
                                                    }
                                                    // First Name (fallback)
                                                    else if (normalizedName.includes('first') || normalizedName.includes('fname')) {
                                                        formData['firstName'] = value;
                                                        if (!formData['legalFirstName']) formData['legalFirstName'] = value;
                                                    }
                                                    // Last Name (fallback)
                                                    else if (normalizedName.includes('last') || normalizedName.includes('lname')) {
                                                        formData['lastName'] = value;
                                                        if (!formData['legalLastName']) formData['legalLastName'] = value;
                                                    }
                                                    // Gender/Sex (fallback)
                                                    else if (normalizedName.includes('gender') || normalizedName.includes('sex')) {
                                                        formData['gender'] = value;
                                                        if (!formData['sexAtBirth']) formData['sexAtBirth'] = value;
                                                    }
                                                    // Room
                                                    else if (normalizedName.includes('room')) {
                                                        formData['room'] = value;
                                                    }
                                                    // Patient ID
                                                    else if (normalizedName.includes('patientid') || normalizedName.includes('patient_id')) {
                                                        formData['patientId'] = value;
                                                    }
                                                    // Solv ID
                                                    else if (normalizedName.includes('solvid') || normalizedName.includes('solv_id')) {
                                                        formData['solvId'] = value;
                                                    }
                                                    // Location
                                                    else if (normalizedName.includes('location')) {
                                                        formData['location'] = value;
                                                        formData['locationId'] = value;
                                                    }
                                                    // Save all other fields with their original name
                                                    else {
                                                        formData[name || input.id] = value;
                                                    }
                                                }
                                            });
                                            
                                            return formData;
                                        }
                                    """)
                                    
                                    # Check if form was submitted (via click listener or form submit)
                                    submission_data = await page.evaluate("""
                    () => {
                                            // Check if we have captured form submission data
                                            if (window._formSubmitData && window._formSubmitTime) {
                                                const timeSinceSubmit = Date.now() - window._formSubmitTime;
                                                // Only return data if it's recent (within last 5 seconds)
                                                if (timeSinceSubmit < 5000) {
                                                    return {
                                                        submitted: true,
                                                        data: window._formSubmitData,
                                                        timestamp: window._formSubmitTime
                                                    };
                                                }
                                            }
                                            
                                            // Fallback: check for buttons with data-form-submitted attribute
                                            const modal = document.querySelector('[role="dialog"]:visible, .modal:visible, [class*="modal"]:not([style*="display: none"])');
                                            if (!modal) {
                                                // Modal might be closing, check if we have last captured data
                                                if (window._lastFormData && Object.keys(window._lastFormData).length > 0) {
                                                    return {
                                                        submitted: true,
                                                        data: window._lastFormData,
                                                        timestamp: Date.now()
                                                    };
                                                }
                                                return { submitted: false };
                                            }
                                            
                                            const submitButtons = modal.querySelectorAll('button[data-form-submitted="true"]');
                                            if (submitButtons.length > 0) {
                                                // Try to get last form data if available
                                                const lastData = window._lastFormData || {};
                                                if (Object.keys(lastData).length > 0) {
                                                    return {
                                                        submitted: true,
                                                        data: lastData,
                                                        timestamp: Date.now()
                                                    };
                                                }
                                                return { submitted: true };
                                            }
                                            
                                            // Check for disabled submit buttons (clicked recently)
                                            const buttons = modal.querySelectorAll('button[type="submit"], button');
                                            for (const btn of buttons) {
                                                const btnText = (btn.textContent || btn.innerText || '').trim().toLowerCase();
                                                if ((btnText.includes('add') || btn.type === 'submit') && btn.disabled) {
                                                    const lastData = window._lastFormData || {};
                                                    return {
                                                        submitted: true,
                                                        data: lastData,
                                                        timestamp: Date.now()
                                                    };
                                                }
                                            }
                                            
                                            return { submitted: false };
                    }
                """)
                                    
                                    # Check if form was submitted
                                    form_submitted = False
                                    submitted_form_data = None
                                    
                                    if submission_data and submission_data.get('submitted'):
                                        form_submitted = True
                                        # Use data from the click listener if available
                                        if submission_data.get('data'):
                                            submitted_form_data = submission_data.get('data')
                                        # Otherwise use the form_data we extracted
                                        elif form_data:
                                            submitted_form_data = form_data
                                    else:
                                        # Fallback: check if modal is closing (form was submitted)
                                        modal_closing = await page.evaluate("""
                                            () => {
                                                const modal = document.querySelector('[role="dialog"], .modal, [class*="modal"]');
                                                if (!modal) return true; // Modal closed
                                                return modal.style.display === 'none' || 
                                                       modal.hasAttribute('hidden') ||
                                                       !modal.offsetParent ||
                                                       window.getComputedStyle(modal).display === 'none';
                                            }
                                        """)
                                        
                                        # Check API requests for recent POST/PUT requests (form submission)
                                        recent_api_call = False
                                        for req in api_requests[-5:]:  # Check last 5 requests
                                            if req.get('method') in ['POST', 'PUT']:
                                                req_time = req.get('time', datetime.now())
                                                time_diff = (datetime.now() - req_time).total_seconds()
                                                if time_diff < 5:  # Request within last 5 seconds
                                                    recent_api_call = True
                                                    break
                                        
                                        # If modal is closing or API call was made, treat as submission
                                        if modal_closing or recent_api_call:
                                            form_submitted = True
                                            submitted_form_data = form_data
                                    
                                    # Always check for form submission, even if form_data is empty or incomplete
                                    # Save data immediately when "Add" button is clicked, regardless of completeness
                                    if form_submitted and submitted_form_data:
                                        # Create a unique submission key - use any available identifiers
                                        first_name = submitted_form_data.get('legalFirstName') or submitted_form_data.get('firstName', '') or submitted_form_data.get('first_name', '')
                                        last_name = submitted_form_data.get('legalLastName') or submitted_form_data.get('lastName', '') or submitted_form_data.get('last_name', '')
                                        submission_key = f"{first_name}-{last_name}-{int(datetime.now().timestamp())}"
                                        if not first_name and not last_name:
                                            # Use timestamp if no names available
                                            submission_key = f"form-{int(datetime.now().timestamp() * 1000)}"
                                        
                                        # Only save if we haven't tracked this submission yet
                                        if submission_key not in form_submission_tracked:
                                                form_submission_tracked.add(submission_key)
                                                submission_id = f"submission-{int(datetime.now().timestamp() * 1000)}"
                                                
                                                # Save form data immediately - ALWAYS save, even if incomplete
                                                print(f"✅ Form submission detected! Submission ID: {submission_id}")
                                                print(f"   Form data captured: {json.dumps(submitted_form_data, indent=2)}")
                                                
                                                # Create patient record from form data
                                                patient_id = submitted_form_data.get('patientId') or submitted_form_data.get('id') or submitted_form_data.get('legalFirstName', '') or submitted_form_data.get('firstName', '') or f"exp-{int(datetime.now().timestamp())}"
                                                
                                                # Try to normalize, but save even if normalization fails
                                                normalized = normalize_patient_data(submitted_form_data, location_id, len(processed_patient_ids))
                                                
                                                # Always save - use normalized if available, otherwise use raw form data
                                                timestamp = int(datetime.now().timestamp() * 1000)
                                                patient_file = data_dir / f"patient-form-{patient_id}-{timestamp}.json"
                                                
                                                if normalized:
                                                    # Use normalized data
                                                    patient_record = {"patients": [normalized]}
                                                    # Also include raw form data for completeness
                                                    patient_record["rawFormData"] = submitted_form_data
                                                else:
                                                    # Normalization failed - save raw form data with basic structure
                                                    print("   ⚠️  Normalization failed, saving raw form data...")
                                                    # Create a basic patient structure from raw data
                                                    raw_patient = {
                                                        "patientId": patient_id,
                                                        "solvId": submitted_form_data.get('solvId', ''),
                                                        "locationId": submitted_form_data.get('locationId') or submitted_form_data.get('location', location_id),
                                                        "firstName": submitted_form_data.get('legalFirstName') or submitted_form_data.get('firstName', ''),
                                                        "lastName": submitted_form_data.get('legalLastName') or submitted_form_data.get('lastName', ''),
                                                        "dob": submitted_form_data.get('dob') or submitted_form_data.get('dateOfBirth', ''),
                                                        "gender": submitted_form_data.get('sexAtBirth') or submitted_form_data.get('gender', ''),
                                                        "room": submitted_form_data.get('room', ''),
                                                        # Include all additional fields
                                                        "mobilePhone": submitted_form_data.get('mobilePhone', ''),
                                                        "reasonForVisit": submitted_form_data.get('reasonForVisit', ''),
                                                        "legalFirstName": submitted_form_data.get('legalFirstName', ''),
                                                        "legalLastName": submitted_form_data.get('legalLastName', ''),
                                                    }
                                                    # Add any other fields that weren't mapped
                                                    for key, value in submitted_form_data.items():
                                                        if key not in raw_patient:
                                                            raw_patient[key] = value
                                                    
                                                    patient_record = {"patients": [raw_patient]}
                                                    patient_record["rawFormData"] = submitted_form_data
                                                    patient_record["normalizationStatus"] = "failed"
                                                
                                                # Save the file
                                                try:
                                                    with open(patient_file, "w", encoding="utf-8") as f:
                                                        json.dump(patient_record, f, indent=2, ensure_ascii=False)
                                                    
                                                    print(f"💾 Form data saved immediately: {patient_file}")
                                                    
                                                    # Also save to patient_data.json
                                                    location_name = get_location_name(location_id)
                                                    save_to_patient_data_json(submitted_form_data, location_id, location_name, '')
                                                    
                                                    # Also display the data
                                                    print(f"\n{'='*60}")
                                                    print(f"📄 FORM SUBMISSION DATA SAVED:")
                                                    print(f"{'='*60}")
                                                    print(json.dumps(patient_record, indent=2, ensure_ascii=False))
                                                    print(f"{'='*60}\n")
                                                except Exception as save_error:
                                                    print(f"❌ Error saving file: {save_error}")
                                                
                                                # Also track for EMR ID monitoring
                                                monitoring_patients[submission_id] = {
                                                    'patient_data': submitted_form_data,
                                                    'submission_time': datetime.now(),
                                                    'form_data': submitted_form_data,
                                                    'patient_id': patient_id
                                                }
                                                
                                                print(f"   Waiting 60-90 seconds for EMR ID...")
                                    
                                    await page.wait_for_timeout(1000)  # Wait a bit before next check
                            except Exception as e:
                                # Continue monitoring even if there's an error
                                await page.wait_for_timeout(1000)
                                continue
                        
                        if not modal_found:
                            modal_visible = False
                        
                        # Wait before next check
                        await page.wait_for_timeout(500)  # Check more frequently
                            
                    except Exception as e:
                        # Continue monitoring even if there's an error
                        await page.wait_for_timeout(2000)
                        continue
            
            # Start monitoring for add patient flow
            asyncio.create_task(monitor_add_patient_flow())
            
            # Main monitoring loop - check for EMR IDs after form submissions
            print("🔄 Running in background mode - monitoring indefinitely...")
            while True:
                # Check API responses for patient data with EMR IDs
                for response in api_responses:
                    try:
                        data = response['data']
                        patients_list = []
                        
                        if isinstance(data, dict):
                            for key in ['patients', 'queue', 'data', 'items', 'results', 'appointments', 'patient']:
                                if key in data:
                                    value = data[key]
                                    if isinstance(value, list):
                                        patients_list = value
                                        break
                                    elif isinstance(value, dict):
                                        patients_list = [value]
                                        break
                            # Check if data itself is a patient object
                            if not patients_list and ('first_name' in data or 'firstName' in data or 'patientId' in data):
                                patients_list = [data]
                        elif isinstance(data, list):
                            patients_list = data
                        
                        for patient in patients_list:
                            if isinstance(patient, dict):
                                pid = extract_patient_id(patient)
                                emr_id = extract_emr_id(patient)
                                
                                if pid and emr_id:
                                    # Found patient with EMR ID - check if we're monitoring it
                                    for submission_id, monitor_info in monitoring_patients.items():
                                        if pid not in processed_patient_ids:
                                            # Check if this matches our submitted form data
                                            form_data = monitor_info.get('form_data', {})
                                            # Try to match by name or other fields
                                            match = False
                                            if form_data.get('firstName') or form_data.get('first_name'):
                                                if (patient.get('firstName') == form_data.get('firstName') or 
                                                    patient.get('first_name') == form_data.get('first_name')):
                                                    match = True
                                            else:
                                                # If we can't match, assume it's our patient if we have recent submissions
                                                wait_time = (datetime.now() - monitor_info['submission_time']).total_seconds()
                                                if wait_time >= emr_wait_min and wait_time <= emr_wait_max + 10:
                                                    match = True
                                            
                                            if match:
                                                wait_time = (datetime.now() - monitor_info['submission_time']).total_seconds()
                                                print(f"✅ EMR ID found for submitted patient: {emr_id} (waited {wait_time:.1f}s)")
                                                
                                                # Update EMR ID in patient_data.json
                                                form_data = monitor_info.get('form_data', {})
                                                update_emr_id_in_patient_data_json(form_data, emr_id, location_id)
                                                
                                                if save_patient_record(patient, pid, location_id):
                                                    processed_patient_ids.add(pid)
                                                    if submission_id in monitoring_patients:
                                                        del monitoring_patients[submission_id]
                    except Exception as e:
                        pass
                
                # Check monitoring patients for timeout
                for submission_id, monitor_info in list(monitoring_patients.items()):
                    wait_time = (datetime.now() - monitor_info['submission_time']).total_seconds()
                    
                    if wait_time >= emr_wait_max:
                        # Maximum wait time reached
                        print(f"⏰ Maximum wait time ({emr_wait_max}s) reached for submission {submission_id}, no EMR ID found - NOT saving")
                        if submission_id in monitoring_patients:
                            del monitoring_patients[submission_id]
                    elif wait_time >= emr_wait_min:
                        # Within wait window
                        if wait_time % 10 < check_interval:
                            print(f"⏳ Waiting for EMR ID... ({wait_time:.0f}s / {emr_wait_max}s)")
                
                # Wait before next check
                await page.wait_for_timeout(check_interval * 1000)
            
            # Note: This loop runs indefinitely in background
            
        except Exception as error:
            print(f"❌ Error during scraping: {error}")
            
            # Take screenshot on error if page is still open
            try:
                if not page.is_closed():
                    error_screenshot_path = screenshots_dir / f"error-{int(datetime.now().timestamp() * 1000)}.png"
                    await page.screenshot(path=str(error_screenshot_path), full_page=True)
                    print(f"📸 Error screenshot saved to {error_screenshot_path}")
            except Exception as screenshot_error:
                print(f"⚠️  Could not take error screenshot: {screenshot_error}")
            
            raise error
            
        finally:
            await context.close()
            print("✅ Browser context closed")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape patient data from Solvhealth queue")
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Queue URL to scrape (optional, can use --location-id or --location-name instead)"
    )
    parser.add_argument(
        "--location-id",
        type=str,
        default=None,
        help="Location ID (e.g., 'AXjwbE'). Use --list-locations to see all locations."
    )
    parser.add_argument(
        "--location-name",
        type=str,
        default=None,
        help="Location name (e.g., 'Exer Urgent Care - Demo'). Use --list-locations to see all locations."
    )
    parser.add_argument(
        "--list-locations",
        action="store_true",
        help="List all available locations and exit"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--no-slow",
        action="store_true",
        help="Disable slow motion (faster execution)"
    )
    parser.add_argument(
        "--auto-fill",
        action="store_true",
        help="Automatically fill and submit a patient form with sample data"
    )
    
    args = parser.parse_args()
    
    # Handle --list-locations flag
    if args.list_locations:
        print("Available Locations:")
        print("=" * 80)
        for name in list_all_locations():
            loc_id = get_location_id(name)
            print(f"  {name:60s} {loc_id}")
        print("=" * 80)
        sys.exit(0)
    
    try:
        asyncio.run(scrape_solvhealth(
            queue_url=args.url,
            location_id=args.location_id,
            location_name=args.location_name,
            headless=args.headless,
            slow_mo=0 if args.no_slow else 500,
            auto_fill=args.auto_fill
        ))
        print("\n✨ Scraping completed successfully!")
        sys.exit(0)
    except Exception as error:
        print(f"\n💥 Scraping failed: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


