from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from datetime import datetime

from models import SessionLocal, Lead
from etl import run_pipeline
from google_sheets import export_to_sheets
from config import CITIES, CLINIC_TYPES

app = FastAPI(
    title="Clinic Lead Generator API",
    description="Generate clinic leads from Google Maps with AI enrichment",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home():
    """Serve Dashboard Frontend"""
    return FileResponse("static/index.html")

@app.post("/generate/{city}/{clinic_type}")
def generate_leads(city: str, clinic_type: str, background_tasks: BackgroundTasks):
    """Generate leads for specific city and clinic type"""
    
    # Validate city
    valid_cities = []
    for cities in CITIES.values():
        valid_cities.extend(cities)
    
    if city not in valid_cities:
        raise HTTPException(status_code=400, detail=f"City '{city}' not found. Available: {valid_cities}")
    
    # Validate clinic type
    if clinic_type not in CLINIC_TYPES:
        raise HTTPException(status_code=400, detail=f"Clinic type '{clinic_type}' not found. Available: {CLINIC_TYPES}")
    
    # Run in background
    background_tasks.add_task(run_pipeline, city, clinic_type)
    
    return {
        "status": "Processing",
        "message": f"Generating leads for {clinic_type} clinics in {city}",
        "city": city,
        "clinic_type": clinic_type
    }

@app.post("/generate-all")
def generate_all_cities(background_tasks: BackgroundTasks):
    """Generate leads for all cities and clinic types"""
    
    total_combinations = 0
    for cities in CITIES.values():
        total_combinations += len(cities) * len(CLINIC_TYPES)
    
    background_tasks.add_task(run_all_combinations)
    
    return {
        "status": "Processing",
        "message": f"Generating leads for all {total_combinations} combinations",
        "total_combinations": total_combinations
    }

@app.get("/leads")
def get_all_leads(
    city: Optional[str] = None,
    country: Optional[str] = None,
    clinic_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """Get all leads with filters"""
    session = SessionLocal()
    
    try:
        query = session.query(Lead)
        
        if city:
            query = query.filter(Lead.city == city)
        if country:
            query = query.filter(Lead.country == country)
        if clinic_type:
            query = query.filter(Lead.clinic_type == clinic_type)
        if status:
            query = query.filter(Lead.call_status == status)
        
        leads = query.limit(limit).all()
        
        return {
            "total": len(leads),
            "leads": [lead.to_dict() for lead in leads]
        }
    
    finally:
        session.close()

@app.get("/leads/{lead_id}")
def get_lead(lead_id: int):
    """Get specific lead by ID"""
    session = SessionLocal()
    
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        return lead.to_dict()
    
    finally:
        session.close()

@app.post("/export")
def export_to_google_sheets():
    """Export all leads to Google Sheets"""
    try:
        success = export_to_sheets()
        
        if success:
            return {"status": "Success", "message": "Leads exported to Google Sheets"}
        else:
            return {
                "status": "Warning", 
                "message": "No leads to export. Please generate leads first using /generate endpoint."
            }
    
    except Exception as e:
        return {
            "status": "Error",
            "message": f"Export failed: {str(e)}"
        }

@app.get("/cities")
def get_cities():
    """Get all available cities"""
    all_cities = []
    for country, cities in CITIES.items():
        for city in cities:
            all_cities.append({
                "city": city,
                "country": country
            })
    return {"cities": all_cities}

@app.get("/clinic-types")
def get_clinic_types():
    """Get all clinic types"""
    return {"clinic_types": CLINIC_TYPES}

@app.get("/stats")
def get_stats():
    """Get system statistics"""
    session = SessionLocal()
    
    try:
        total_leads = session.query(Lead).count()
        
        country_counts = {}
        for country in set([l.country for l in session.query(Lead).all()]):
            count = session.query(Lead).filter(Lead.country == country).count()
            country_counts[country] = count
        
        return {
            "total_leads": total_leads,
            "by_country": country_counts,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    finally:
        session.close()

# Background task
def run_all_combinations():
    """Run all combinations in background"""
    from etl import run_pipeline
    from google_sheets import export_to_sheets
    
    results = []
    
    for country, cities in CITIES.items():
        for city in cities:
            for clinic_type in CLINIC_TYPES:
                try:
                    result = run_pipeline(city, clinic_type)
                    results.append(result)
                except Exception as e:
                    print(f"Error: {city} - {clinic_type}: {e}")
    
    # Final export
    export_to_sheets()
    
    print(f"Completed all combinations. Total runs: {len(results)}")

@app.on_event("startup")
def startup_event():
    """Run on server startup"""
    print(" Clinic Lead Generator API Started")
    print(f" Target Cities: {len(sum(CITIES.values(), []))} cities")
    print(f" Clinic Types: {len(CLINIC_TYPES)} types")
    print(f" Total Combinations: {len(sum(CITIES.values(), [])) * len(CLINIC_TYPES)}")