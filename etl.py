import re
import time
import requests
import urllib.parse
from html.parser import HTMLParser
from datetime import datetime
from openai import OpenAI
from apify_client import ApifyClient
from config import APIFY_API_TOKEN, GROQ_API_KEY
from models import Lead, SessionLocal

# Initialize APIs
apify_client = ApifyClient(APIFY_API_TOKEN)

# Initialize Groq with OpenAI client (recommended by Groq docs)
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

class ClinicWebsiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.ignore_tags = {'script', 'style', 'head', 'meta', 'header', 'footer', 'nav'}
        self.current_tag = None
        self.social_links = []
        self.emails = []
        self.booking_links = []
        self.phones = []

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        attrs_dict = dict(attrs)
        href = attrs_dict.get('href', '').strip()
        if href:
            # Look for social media links
            if any(domain in href.lower() for domain in ['instagram.com', 'facebook.com', 'twitter.com', 'linkedin.com']):
                self.social_links.append(href)
            # Look for email links
            elif href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0].strip()
                if email:
                    self.emails.append(email)
            # Look for phone links
            elif href.startswith('tel:'):
                phone = href.replace('tel:', '').strip()
                if phone:
                    self.phones.append(phone)
            # Look for booking links
            elif any(k in href.lower() for k in ['book', 'appointment', 'reserve', 'schedule', 'booking', 'contact']):
                self.booking_links.append(href)

    def handle_endtag(self, tag):
        self.current_tag = None

    def handle_data(self, data):
        if self.current_tag not in self.ignore_tags:
            text = data.strip()
            if text:
                text = re.sub(r'\s+', ' ', text)
                self.text_parts.append(text)

    def get_data(self):
        return {
            "text": " ".join(self.text_parts)[:2000],  # Get first 2000 characters
            "socials": list(set(self.social_links))[:5],
            "emails": list(set(self.emails))[:3],
            "phones": list(set(self.phones))[:3],
            "booking_links": list(set(self.booking_links))[:3]
        }

def scrape_clinic_website(url):
    """Fetch website HTML and parse visible text/links"""
    if not url:
        return None
    
    # Ensure URL has protocol
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        print(f"Scraping website: {url} ...")
        response = requests.get(url, timeout=10, headers=headers)
        if response.status_code == 200:
            parser = ClinicWebsiteParser()
            parser.feed(response.text)
            parsed_data = parser.get_data()
            
            # Resolve relative booking links
            resolved_bookings = []
            for link in parsed_data['booking_links']:
                if link.startswith('/'):
                    resolved_bookings.append(urllib.parse.urljoin(url, link))
                else:
                    resolved_bookings.append(link)
            parsed_data['booking_links'] = resolved_bookings
            
            return parsed_data
        else:
            print(f"Failed to fetch {url}: Status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error scraping website {url}: {e}")
        return None

def extract_address_string(address_data):
    """Extract address string from Apify address object"""
    if isinstance(address_data, dict):
        return address_data.get('addressString', '')
    return str(address_data) if address_data else ''

def extract_from_google_maps(city, clinic_type):
    """Extract clinics using Apify Google Maps Scraper"""
    try:
        # Run Apify Actor
        run = apify_client.actor("yash.m.bhayani~google-map-scraper").call(
            run_input={
                "searchText": f"{clinic_type} clinics in {city}",
                "pages": 3  # 3 pages = ~60 results
            }
        )
        
        # Get results from dataset
        dataset = apify_client.dataset(run.default_dataset_id)
        clinics = []
        
        # Get items from dataset
        items = dataset.list_items().items
        
        for item in items:
            clinic = {
                'clinic_name': item.get('title', '') or item.get('name', ''),
                'clinic_type': clinic_type,
                'country': city_to_country(city),
                'city': city,
                'address': extract_address_string(item.get('address', {})),
                'phone_number': item.get('phone', ''),
                'website_url': item.get('website', ''),
                'google_rating': str(item.get('rating', '')),
                'reviews_count': item.get('reviewsCount', 0),
                'doctor_name': '',
                'email': '',
                'social_links': '',
                'appointment_method': '',
                'automation_status': '',
                'notes': ''
            }
            clinics.append(clinic)
        
        return clinics
    
    except Exception as e:
        print(f"Error extracting clinics: {e}")
        return []

def city_to_country(city):
    """Map city to country"""
    city_map = {
        'London': 'UK', 'Manchester': 'UK', 'Birmingham': 'UK', 'Leeds': 'UK', 'Bristol': 'UK',
        'Dubai': 'UAE', 'Abu Dhabi': 'UAE', 'Sharjah': 'UAE',
        'Islamabad': 'Pakistan', 'Rawalpindi': 'Pakistan', 'Lahore': 'Pakistan', 'Karachi': 'Pakistan',
        'Sydney': 'Australia', 'Melbourne': 'Australia', 'Brisbane': 'Australia'
    }
    return city_map.get(city, 'Unknown')

def transform_and_enrich(clinics):
    """Clean data and enrich with Groq"""
    enriched_clinics = []
    
    for clinic in clinics:
        try:
            # Basic cleaning
            clinic['clinic_name'] = clean_name(clinic['clinic_name'])
            clinic['phone_number'] = clean_phone(clinic['phone_number'])
            
            # Enrich with Groq if website available
            if clinic['website_url']:
                # Scrape website content
                scraped = scrape_clinic_website(clinic['website_url'])
                
                # Fallback email/phone check if scraped
                if scraped:
                    if not clinic['phone_number'] and scraped['phones']:
                        clinic['phone_number'] = clean_phone(scraped['phones'][0])
                    if scraped['emails']:
                        clinic['email'] = scraped['emails'][0]
                
                # Enrich with Groq
                enrichment = groq_enrichment(clinic['website_url'], clinic['clinic_name'], scraped)
                
                if enrichment.get('email'):
                    clinic['email'] = enrichment.get('email')
                clinic['doctor_name'] = enrichment.get('doctor_name', '')
                clinic['appointment_method'] = enrichment.get('appointment_method', 'Unknown')
                clinic['automation_status'] = enrichment.get('automation_status', 'Unknown')
                clinic['social_links'] = enrichment.get('social_links', '')
                
                # Wait 2 seconds to avoid rate limit
                time.sleep(2)
            else:
                clinic['appointment_method'] = 'Phone'
                clinic['automation_status'] = 'Manual'
            
            # Set priority based on ratings
            if clinic['google_rating']:
                try:
                    rating = float(clinic['google_rating'])
                    if rating >= 4.5:
                        clinic['lead_priority'] = 'High'
                    elif rating >= 3.5:
                        clinic['lead_priority'] = 'Medium'
                    else:
                        clinic['lead_priority'] = 'Low'
                except ValueError:
                    clinic['lead_priority'] = 'Medium'
            else:
                clinic['lead_priority'] = 'Medium'
            
            enriched_clinics.append(clinic)
            
        except Exception as e:
            print(f"Error enriching clinic {clinic.get('clinic_name')}: {e}")
            continue
    
    return enriched_clinics

def clean_name(name):
    """Clean clinic name"""
    if not name:
        return ''
    name = ' '.join(name.split())
    return name

def clean_phone(phone):
    """Clean phone number"""
    if not phone:
        return ''
    phone = re.sub(r'[^0-9+]', '', phone)
    return phone

def groq_enrichment(website, name, scraped_data=None):
    """Use Groq to find email, doctor name, appointment method, automation status, socials"""
    try:
        if scraped_data:
            raw_emails = ", ".join(scraped_data.get('emails', []))
            raw_phones = ", ".join(scraped_data.get('phones', []))
            raw_socials = ", ".join(scraped_data.get('socials', []))
            raw_bookings = ", ".join(scraped_data.get('booking_links', []))
            page_text = scraped_data.get('text', '')
            
            prompt = f"""
            Analyze the following scraped clinic details and website text snippet:
            Clinic Name: {name}
            Website URL: {website}
            
            Scraped Raw Emails: {raw_emails if raw_emails else 'None found'}
            Scraped Raw Phones: {raw_phones if raw_phones else 'None found'}
            Scraped Raw Socials: {raw_socials if raw_socials else 'None found'}
            Scraped Booking/Contact Links: {raw_bookings if raw_bookings else 'None found'}
            
            Website Visible Text Snippet:
            \"\"\"{page_text}\"\"\"
            
            Tasks:
            1. Identify a verified Email address for the clinic. If none is in the scraped emails, check if one appears in the text snippet.
            2. Identify any Doctor, Practitioner, or Owner name mentioned on the page (e.g. Dr. John Doe).
            3. Classify the Clinic Appointment method from this list:
               - 'Phone' (if they only list a phone number)
               - 'WhatsApp' (if they have WhatsApp links or chat widgets)
               - 'Website Booking' (if they have a scheduling form or booking page)
               - 'Online System' (if they use platforms like HotDoc, Halaxy, Zocdoc, or external booking portals)
               - 'Social Media' (if booking via Instagram/Facebook)
               - 'Walk-in' or 'Email'
               Select the most advanced option present (Online System > Website Booking > WhatsApp > Phone > Walk-in).
            4. Determine the Automation Status:
               - 'Automated' (if using Online System or instant booking widget)
               - 'Semi-Automated' (if using a Website Booking form, WhatsApp chat request, or contact form)
               - 'Manual' (if appointment is only by Phone, Email, or Walk-in)
            5. Provide social media links found (Facebook/Instagram URLs, separate by comma).
            
            Return ONLY a valid JSON object in this exact format:
            {{
                "email": "extracted email or empty",
                "doctor_name": "doctor name or empty",
                "appointment_method": "Phone/WhatsApp/Website Booking/Online System/Walk-in/Email",
                "automation_status": "Automated/Semi-Automated/Manual",
                "social_links": "comma-separated social links or empty"
            }}
            """
        else:
            prompt = f"""
            Analyze this clinic website: {website}
            Clinic name: {name}
            
            Extract the following:
            1. Email address (if available)
            2. Doctor/Owner name (if available)
            3. Appointment method (Phone/WhatsApp/Website Booking/Online System/Social Media/Walk-in)
            4. Automation status (Manual/Semi-Automated/Automated)
            5. Social media links (Instagram/Facebook)
            
            Return as JSON format:
            {{
                "email": "email or empty",
                "doctor_name": "name or empty",
                "appointment_method": "method",
                "automation_status": "status",
                "social_links": "links or empty"
            }}
            """
        
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",  # ✅ Required model
            messages=[
                {"role": "system", "content": "You extract clinic information from website text or details."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=200
        )
        
        # Parse response
        import json, re as _re
        content = response.choices[0].message.content
        # Extract JSON from response
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end != 0:
            json_str = content[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback: extract individual fields with regex
                def _extract(key):
                    m = _re.search(rf'"{key}"\s*:\s*"([^"]*)"', json_str)
                    return m.group(1) if m else ''
                return {
                    'email': _extract('email'),
                    'doctor_name': _extract('doctor_name'),
                    'appointment_method': _extract('appointment_method') or 'Unknown',
                    'automation_status': _extract('automation_status') or 'Unknown',
                    'social_links': _extract('social_links')
                }
        else:
            return {
                'email': '',
                'doctor_name': '',
                'appointment_method': 'Unknown',
                'automation_status': 'Unknown',
                'social_links': ''
            }
            
    except Exception as e:
        print(f"Groq enrichment error: {e}")
        return {
            'email': '',
            'doctor_name': '',
            'appointment_method': 'Unknown',
            'automation_status': 'Unknown',
            'social_links': ''
        }

def load_to_database(clinics):
    """Load enriched clinics to database"""
    session = SessionLocal()
    added_count = 0
    
    try:
        for clinic_data in clinics:
            # Check duplicate
            existing = session.query(Lead).filter_by(
                clinic_name=clinic_data['clinic_name'],
                city=clinic_data['city']
            ).first()
            
            if existing:
                continue
            
            lead = Lead(
                clinic_name=clinic_data['clinic_name'],
                clinic_type=clinic_data['clinic_type'],
                country=clinic_data['country'],
                city=clinic_data['city'],
                address=clinic_data['address'],
                phone_number=clinic_data['phone_number'],
                email=clinic_data.get('email', ''),
                website_url=clinic_data['website_url'],
                doctor_name=clinic_data.get('doctor_name', ''),
                social_links=clinic_data.get('social_links', ''),
                appointment_method=clinic_data.get('appointment_method', ''),
                automation_status=clinic_data.get('automation_status', ''),
                google_rating=clinic_data['google_rating'],
                reviews_count=clinic_data['reviews_count'],
                lead_priority=clinic_data.get('lead_priority', 'Medium'),
                notes=clinic_data.get('notes', ''),
                call_status='New'
            )
            
            session.add(lead)
            added_count += 1
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"Database error: {e}")
    finally:
        session.close()
    
    return added_count

def run_pipeline(city, clinic_type):
    """Main ETL pipeline — extract, enrich, save to DB, then auto-sync to Google Sheets"""
    print(f"Starting ETL for {clinic_type} clinics in {city}")
    
    # Extract
    clinics = extract_from_google_maps(city, clinic_type)
    print(f"Extracted {len(clinics)} clinics")
    
    # Transform & Enrich
    enriched = transform_and_enrich(clinics)
    print(f"Enriched {len(enriched)} clinics")
    
    # Load to database
    added = load_to_database(enriched)
    print(f"Added {added} new clinics to database")
    
    # Auto-export to Google Sheets after every pipeline run
    if added > 0:
        print(f"Auto-syncing {added} new lead(s) to Google Sheets...")
        try:
            from google_sheets import export_to_sheets
            export_to_sheets()
            print("Google Sheets auto-sync complete!")
        except Exception as e:
            print(f"Google Sheets auto-sync failed: {e}")
    else:
        print("No new leads added — Google Sheets sync skipped.")
    
    return {
        "city": city,
        "clinic_type": clinic_type,
        "total_found": len(clinics),
        "total_enriched": len(enriched),
        "total_added": added,
        "clinics": enriched
    }