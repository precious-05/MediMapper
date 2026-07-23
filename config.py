import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
#GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///leads.db")
GOOGLE_SHEETS_CREDS = os.getenv("GOOGLE_SHEETS_CREDS", "credentials.json")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN") 

# Cities Configuration
CITIES = {
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Bristol"],
    "UAE": ["Dubai", "Abu Dhabi", "Sharjah"],
    "Pakistan": ["Islamabad", "Rawalpindi", "Lahore", "Karachi"],
    "Australia": ["Sydney", "Melbourne", "Brisbane"]
}

CLINIC_TYPES = [
    "Dental", "Aesthetic", "Skin", "Cosmetic", 
    "Physiotherapy", "Hair Transplant", "Eye", 
    "Private Medical", "Wellness & Health"
]