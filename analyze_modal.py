#!/usr/bin/env python3
"""
Analyze the Add Patient modal structure to understand form fields.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from datetime import datetime
from locations import get_queue_url, DEFAULT_LOCATION_ID

async def analyze_modal_structure():
    """Click Add Patient, analyze modal structure, and display all form fields."""
    
    print("🔍 Starting modal structure analysis...")
    
    base_dir = Path(__file__).parent
    user_data_dir = base_dir / ".browser-data"
    
    async with async_playwright() as p:
        # Use persistent browser context
        browser_launcher = None
        try:
            browser_launcher = p.chrome
            print("✅ Using Chrome browser")
        except Exception:
            browser_launcher = p.chromium
            print("✅ Using Chromium browser")
        
        context = await browser_launcher.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            slow_mo=500,
            viewport=None
        )
        
        pages = context.pages
        if pages:
            page = pages[0]
        else:
            page = await context.new_page()
        
        try:
            # Navigate to queue page (using default location)
            queue_url = get_queue_url()
            print(f"📡 Navigating to: {queue_url}")
            await page.goto(queue_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            print(f"✅ Page loaded: {page.url}")
            
            # Find and click "Add Patient" button
            print("\n🔍 Looking for 'Add Patient' button...")
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
                        print(f"✅ Found button with selector: {selector}")
                        await button.click()
                        add_button_clicked = True
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue
            
            if not add_button_clicked:
                print("❌ Could not find 'Add Patient' button")
                return
            
            # Wait for modal to appear
            print("\n⏳ Waiting for modal to appear...")
            await page.wait_for_timeout(3000)
            
            # Analyze modal structure
            print("\n" + "="*70)
            print("📊 MODAL STRUCTURE ANALYSIS")
            print("="*70)
            
            modal_info = await page.evaluate("""
                () => {
                    const modal = document.querySelector('[role="dialog"]:visible, .modal:visible, [class*="modal"]:not([style*="display: none"])');
                    if (!modal) {
                        return { error: "Modal not found" };
                    }
                    
                    const info = {
                        modalFound: true,
                        modalClasses: modal.className || '',
                        modalId: modal.id || '',
                        modalTag: modal.tagName,
                        modalAttributes: {},
                        fields: [],
                        labels: [],
                        buttons: []
                    };
                    
                    // Get modal attributes
                    Array.from(modal.attributes).forEach(attr => {
                        info.modalAttributes[attr.name] = attr.value;
                    });
                    
                    // Find all form inputs, selects, textareas
                    const inputs = modal.querySelectorAll('input, select, textarea');
                    inputs.forEach((input, index) => {
                        const fieldInfo = {
                            index: index,
                            tag: input.tagName,
                            type: input.type || input.tagName.toLowerCase(),
                            name: input.name || '',
                            id: input.id || '',
                            placeholder: input.placeholder || '',
                            value: input.value || '',
                            className: input.className || '',
                            required: input.required || false,
                            disabled: input.disabled || false,
                            ariaLabel: input.getAttribute('aria-label') || '',
                            dataAttributes: {}
                        };
                        
                        // Get data attributes
                        Array.from(input.attributes).forEach(attr => {
                            if (attr.name.startsWith('data-')) {
                                fieldInfo.dataAttributes[attr.name] = attr.value;
                            }
                        });
                        
                        // For select elements, get options
                        if (input.tagName === 'SELECT') {
                            fieldInfo.options = [];
                            Array.from(input.options).forEach(opt => {
                                fieldInfo.options.push({
                                    value: opt.value,
                                    text: opt.text,
                                    selected: opt.selected
                                });
                            });
                        }
                        
                        // Try to find associated label
                        let label = null;
                        if (input.id) {
                            label = document.querySelector(`label[for="${input.id}"]`);
                        }
                        if (!label) {
                            label = input.closest('label') || input.parentElement?.querySelector('label');
                        }
                        if (!label) {
                            // Try to find label by text content near input
                            const parent = input.closest('div, fieldset, form');
                            if (parent) {
                                label = parent.querySelector('label');
                            }
                        }
                        
                        if (label) {
                            fieldInfo.labelText = label.textContent?.trim() || '';
                            fieldInfo.labelFor = label.getAttribute('for') || '';
                        }
                        
                        info.fields.push(fieldInfo);
                    });
                    
                    // Find all labels
                    const labels = modal.querySelectorAll('label');
                    labels.forEach(label => {
                        info.labels.push({
                            text: label.textContent?.trim() || '',
                            for: label.getAttribute('for') || '',
                            html: label.innerHTML
                        });
                    });
                    
                    // Find all buttons
                    const buttons = modal.querySelectorAll('button');
                    buttons.forEach(btn => {
                        info.buttons.push({
                            text: btn.textContent?.trim() || '',
                            type: btn.type || '',
                            className: btn.className || '',
                            id: btn.id || '',
                            disabled: btn.disabled || false,
                            ariaLabel: btn.getAttribute('aria-label') || ''
                        });
                    });
                    
                    // Get modal text content (for context)
                    info.modalText = modal.textContent?.substring(0, 500) || '';
                    
                    return info;
                }
            """)
            
            if modal_info.get('error'):
                print(f"❌ {modal_info['error']}")
                return
            
            print(f"\n✅ Modal Found!")
            print(f"   Tag: {modal_info.get('modalTag', 'N/A')}")
            print(f"   Classes: {modal_info.get('modalClasses', 'N/A')}")
            print(f"   ID: {modal_info.get('modalId', 'N/A')}")
            
            print(f"\n📋 Form Fields Found: {len(modal_info.get('fields', []))}")
            print("-" * 70)
            
            for i, field in enumerate(modal_info.get('fields', []), 1):
                print(f"\n{i}. Field #{field.get('index', i-1)}:")
                print(f"   Tag: {field.get('tag', 'N/A')}")
                print(f"   Type: {field.get('type', 'N/A')}")
                print(f"   Name: {field.get('name', 'N/A') or 'N/A'}")
                print(f"   ID: {field.get('id', 'N/A') or 'N/A'}")
                print(f"   Placeholder: {field.get('placeholder', 'N/A') or 'N/A'}")
                print(f"   Label: {field.get('labelText', 'N/A') or 'N/A'}")
                print(f"   Value: {field.get('value', 'N/A') or 'N/A'}")
                print(f"   Required: {field.get('required', False)}")
                print(f"   Disabled: {field.get('disabled', False)}")
                if field.get('ariaLabel'):
                    print(f"   Aria Label: {field.get('ariaLabel')}")
                if field.get('dataAttributes'):
                    print(f"   Data Attributes: {field.get('dataAttributes')}")
                if field.get('options'):
                    print(f"   Options ({len(field.get('options', []))}):")
                    for opt in field.get('options', [])[:5]:  # Show first 5
                        print(f"      - {opt.get('text', 'N/A')} (value: {opt.get('value', 'N/A')})")
            
            print(f"\n📋 Labels Found: {len(modal_info.get('labels', []))}")
            print("-" * 70)
            for label in modal_info.get('labels', []):
                if label.get('text'):
                    print(f"   - '{label.get('text')}' (for: {label.get('for', 'N/A')})")
            
            print(f"\n📋 Buttons Found: {len(modal_info.get('buttons', []))}")
            print("-" * 70)
            for btn in modal_info.get('buttons', []):
                print(f"   - '{btn.get('text', 'N/A')}' (type: {btn.get('type', 'N/A')})")
            
            # Save analysis to file
            data_dir = base_dir / "scraped-data"
            data_dir.mkdir(exist_ok=True)
            analysis_file = data_dir / f"modal-analysis-{int(datetime.now().timestamp() * 1000)}.json"
            
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(modal_info, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Analysis saved to: {analysis_file}")
            
            print("\n" + "="*70)
            print("✅ Analysis Complete!")
            print("="*70)
            
            # Keep browser open for inspection
            print("\n⏳ Keeping browser open for 30 seconds for manual inspection...")
            await page.wait_for_timeout(30000)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            print("\n✅ Analysis complete. Browser will remain open.")
            # Don't close - let user inspect

if __name__ == "__main__":
    asyncio.run(analyze_modal_structure())

