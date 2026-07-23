import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import GOOGLE_SHEETS_CREDS
from models import SessionLocal, Lead

def get_google_sheet_client():
    """Connect to Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDS, scope)
        client = gspread.authorize(creds)
        return client
    
    except Exception as e:
        print(f"Google Sheets connection error: {e}")
        return None

def create_or_get_sheet():
    """Create or get Google Sheet"""
    client = get_google_sheet_client()
    if not client:
        return None
    
    try:
        # Try to open existing sheet
        sheet = client.open('Clinic Data')
        print("Existing sheet found: Clinic Data")
        return sheet.sheet1
    
    except gspread.SpreadsheetNotFound:
        # Create new sheet
        print("Creating new sheet...")
        sheet = client.create('Clinic Data')
        print("New sheet created")
        return sheet.sheet1

def export_to_sheets():
    """Export all leads from database to Google Sheets"""
    worksheet = create_or_get_sheet()
    if not worksheet:
        print("Failed to connect to Google Sheets")
        return False
    
    session = SessionLocal()
    
    try:
        # Get all leads
        leads = session.query(Lead).all()
        
        headers = [
            'Lead ID', 'Clinic Name', 'Clinic Type', 'Country', 'City',
            'Address', 'Appointment Method', 'Phone Number', 'Email',
            'Website Available', 'Website URL', 'Doctor/Owner Name',
            'Social Media Links', 'Automation Status', 'Google Rating',
            'Reviews Count', 'Lead Priority', 'Notes', 'Call Status',
            'Follow-up Date'
        ]
        
        # Prepare all data to write
        data = [headers]
        for lead in leads:
            row = [
                lead.id,
                lead.clinic_name,
                lead.clinic_type,
                lead.country,
                lead.city,
                lead.address if lead.address else 'N/A',
                lead.appointment_method if lead.appointment_method else 'N/A',
                lead.phone_number if lead.phone_number else 'N/A',
                lead.email if lead.email else 'N/A',
                'Yes' if lead.website_url else 'No',
                lead.website_url if lead.website_url else 'N/A',
                lead.doctor_name if lead.doctor_name else 'N/A',
                lead.social_links if lead.social_links else 'N/A',
                lead.automation_status if lead.automation_status else 'N/A',
                lead.google_rating if lead.google_rating else 'N/A',
                lead.reviews_count if lead.reviews_count else 0,
                lead.lead_priority if lead.lead_priority else 'Medium',
                lead.notes if lead.notes else 'N/A',
                lead.call_status if lead.call_status else 'New',
                str(lead.follow_up_date) if lead.follow_up_date else 'N/A'
            ]
            data.append(row)
        
        print(f"Exporting {len(leads)} leads to Google Sheets in a single batch...")
        
        # Clear the entire sheet
        worksheet.clear()
        
        # Update sheet starting from A1
        worksheet.update('A1', data)
        print("Export completed successfully!")
        return True
    
    except Exception as e:
        print(f"Export error: {e}")
        return False
    
    finally:
        session.close()

def clear_google_sheets():
    """Clear all data from Google Sheets (keep headers)"""
    worksheet = create_or_get_sheet()
    if not worksheet:
        return False
    
    try:
        headers = [
            'Lead ID', 'Clinic Name', 'Clinic Type', 'Country', 'City',
            'Address', 'Appointment Method', 'Phone Number', 'Email',
            'Website Available', 'Website URL', 'Doctor/Owner Name',
            'Social Media Links', 'Automation Status', 'Google Rating',
            'Reviews Count', 'Lead Priority', 'Notes', 'Call Status',
            'Follow-up Date'
        ]
        print("Clearing Google Sheets...")
        worksheet.clear()
        worksheet.update('A1', [headers])
        print("Google Sheets cleared (headers kept)")
        return True
    
    except Exception as e:
        print(f"Clear error: {e}")
        return False