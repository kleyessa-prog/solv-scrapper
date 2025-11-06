#!/usr/bin/env python3
"""
Automate filling the Add Patient form with sample data.
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from datetime import datetime
from locations import get_queue_url, DEFAULT_LOCATION_ID

async def auto_fill_patient_form():
    """Automate clicking Add Patient, filling form, and submitting."""
    
    print("🚀 Starting automated form filling...")
    
    base_dir = Path(__file__).parent
    user_data_dir = base_dir / ".browser-data"
    
    async with async_playwright() as p:
        # Use regular browser launch (non-persistent) to avoid conflicts
        browser_launcher = None
        try:
            browser_launcher = p.chrome
            print("✅ Using Chrome browser")
        except Exception:
            browser_launcher = p.chromium
            print("✅ Using Chromium browser")
        
        # Launch new browser instance (non-persistent to avoid conflicts)
        print("🚀 Launching browser...")
        browser = await browser_launcher.launch(
            headless=False,
            slow_mo=500
        )
        context = await browser.new_context(
            viewport=None,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Navigate to queue page (using default location)
            queue_url = get_queue_url()
            print(f"📡 Navigating to queue page: {queue_url}")
            await page.goto(queue_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            print(f"✅ Page loaded: {page.url}")
            
            # Wait for page to be fully loaded
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Find and click "Add Patient" button
            print("🔍 Looking for 'Add Patient' button...")
            
            # Try multiple selectors for the Add Patient button
            add_patient_selectors = [
                "button:has-text('Add Patient')",
                "button:has-text('Add patient')",
                "button:has-text('Add')",
                "[data-testid*='add']",
                "[class*='add-patient']",
                "[class*='AddPatient']",
                "button[aria-label*='Add']",
                "button[aria-label*='Patient']",
            ]
            
            add_button_clicked = False
            for selector in add_patient_selectors:
                try:
                    button = page.locator(selector).first
                    if await button.is_visible(timeout=2000):
                        print(f"✅ Found 'Add Patient' button with selector: {selector}")
                        await button.click()
                        add_button_clicked = True
                        print("✅ Clicked 'Add Patient' button")
                        await page.wait_for_timeout(2000)
                        break
                except Exception as e:
                    continue
            
            if not add_button_clicked:
                print("⚠️  Could not find 'Add Patient' button. Trying to find any button with 'add' in text...")
                # Try to find any button with 'add' in it
                buttons = await page.locator("button").all()
                for btn in buttons:
                    text = await btn.text_content()
                    if text and 'add' in text.lower():
                        print(f"✅ Found button with text: {text}")
                        await btn.click()
                        add_button_clicked = True
                        await page.wait_for_timeout(2000)
                        break
            
            if not add_button_clicked:
                print("❌ Could not find 'Add Patient' button")
                return
            
            # Wait for modal to appear
            print("⏳ Waiting for modal to appear...")
            await page.wait_for_timeout(2000)
            
            # Try to find modal
            modal_selectors = [
                "[role='dialog']",
                ".modal",
                "[class*='modal']",
                "[class*='Modal']",
                "[class*='dialog']",
                "[class*='Dialog']"
            ]
            
            modal_found = False
            for selector in modal_selectors:
                try:
                    modal = page.locator(selector).first
                    if await modal.is_visible(timeout=3000):
                        print(f"✅ Modal found with selector: {selector}")
                        modal_found = True
                        break
                except:
                    continue
            
            if not modal_found:
                print("⚠️  Modal not found, but continuing...")
            
            # Fill form with sample data
            print("📝 Filling form with sample data...")
            
            sample_data = {
                "firstName": "John",
                "lastName": "Doe",
                "dob": "1990-01-15",
                "gender": "M",
                "room": "101"
            }
            
            # Try to fill first name
            first_name_selectors = [
                "input[name*='first']",
                "input[id*='first']",
                "input[placeholder*='First']",
                "input[placeholder*='first']",
                "input[data-field*='first']"
            ]
            
            for selector in first_name_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible(timeout=1000):
                        await field.fill(sample_data["firstName"])
                        print(f"✅ Filled first name: {sample_data['firstName']}")
                        break
                except:
                    continue
            
            # Try to fill last name
            last_name_selectors = [
                "input[name*='last']",
                "input[id*='last']",
                "input[placeholder*='Last']",
                "input[placeholder*='last']",
                "input[data-field*='last']"
            ]
            
            for selector in last_name_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible(timeout=1000):
                        await field.fill(sample_data["lastName"])
                        print(f"✅ Filled last name: {sample_data['lastName']}")
                        break
                except:
                    continue
            
            # Try to fill DOB
            dob_selectors = [
                "input[name*='dob']",
                "input[name*='birth']",
                "input[name*='date']",
                "input[type='date']",
                "input[id*='dob']",
                "input[id*='birth']",
                "input[placeholder*='Date']",
                "input[placeholder*='DOB']"
            ]
            
            for selector in dob_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible(timeout=1000):
                        await field.fill(sample_data["dob"])
                        print(f"✅ Filled DOB: {sample_data['dob']}")
                        break
                except:
                    continue
            
            # Try to fill gender
            gender_selectors = [
                "select[name*='gender']",
                "select[id*='gender']",
                "select[name*='sex']",
                "input[type='radio'][value='M']",
                "input[type='radio'][value='Male']"
            ]
            
            for selector in gender_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible(timeout=1000):
                        if field.evaluate("el => el.tagName") == "SELECT":
                            await field.select_option(sample_data["gender"])
                        else:
                            await field.click()
                        print(f"✅ Filled gender: {sample_data['gender']}")
                        break
                except:
                    continue
            
            # Try to fill room
            room_selectors = [
                "input[name*='room']",
                "input[id*='room']",
                "input[placeholder*='Room']",
                "input[data-field*='room']"
            ]
            
            for selector in room_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible(timeout=1000):
                        await field.fill(sample_data["room"])
                        print(f"✅ Filled room: {sample_data['room']}")
                        break
                except:
                    continue
            
            # Set location to "demo"
            print("🔍 Setting location to 'demo'...")
            location_selectors = [
                "select[name*='location']",
                "select[id*='location']",
                "select[data-field*='location']",
                "input[name*='location']",
                "input[id*='location']"
            ]
            
            for selector in location_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible(timeout=1000):
                        tag = await field.evaluate("el => el.tagName")
                        if tag == "SELECT":
                            # Try to select "demo" option
                            try:
                                await field.select_option("demo")
                                print("✅ Selected location: demo")
                            except:
                                # Try to select by text
                                options = await field.locator("option").all()
                                for opt in options:
                                    text = await opt.text_content()
                                    if text and "demo" in text.lower():
                                        await opt.click()
                                        print("✅ Selected location: demo")
                                        break
                        else:
                            await field.fill("demo")
                            print("✅ Filled location: demo")
                        break
                except:
                    continue
            
            await page.wait_for_timeout(1000)
            
            # Click Add/Submit button
            print("🔍 Looking for 'Add' button to submit form...")
            
            submit_selectors = [
                "button[type='submit']",
                "button:has-text('Add')",
                "button:has-text('Submit')",
                "button:has-text('Save')",
                "button[class*='submit']",
                "button[class*='add']"
            ]
            
            submit_clicked = False
            for selector in submit_selectors:
                try:
                    button = page.locator(selector).first
                    if await button.is_visible(timeout=2000):
                        # Make sure it's in the modal
                        modal = button.locator("xpath=ancestor::*[@role='dialog' or contains(@class, 'modal')]")
                        if await modal.count() > 0:
                            print(f"✅ Found submit button with selector: {selector}")
                            await button.click()
                            submit_clicked = True
                            print("✅ Clicked 'Add' button - form submitted!")
                            await page.wait_for_timeout(3000)
                            break
                except:
                    continue
            
            if not submit_clicked:
                print("⚠️  Could not find submit button in modal, trying alternative...")
                # Try to find any button in modal
                try:
                    modal = page.locator("[role='dialog'], .modal").first
                    if await modal.is_visible():
                        buttons = await modal.locator("button").all()
                        for btn in buttons:
                            text = await btn.text_content()
                            if text and ('add' in text.lower() or 'submit' in text.lower() or 'save' in text.lower()):
                                await btn.click()
                                print(f"✅ Clicked button: {text}")
                                submit_clicked = True
                                await page.wait_for_timeout(3000)
                                break
                except:
                    pass
            
            if submit_clicked:
                print("✅ Form submission completed!")
                print("⏳ Waiting for data to be saved by the scraper...")
                await page.wait_for_timeout(5000)
            else:
                print("⚠️  Could not find submit button")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            print("✅ Form filling completed!")
            # Keep browser open if connected to existing, otherwise close
            try:
                if hasattr(browser, 'contexts') and browser.contexts:
                    print("✅ Keeping browser open (connected to existing instance)")
                else:
                    await browser.close()
            except:
                pass


if __name__ == "__main__":
    asyncio.run(auto_fill_patient_form())

