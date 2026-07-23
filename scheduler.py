from celery import Celery
from celery.schedules import crontab
import asyncio
import os
from config import CITIES, CLINIC_TYPES

# Celery setup with Redis 5 compatibility
app = Celery('scheduler',
             broker='redis://localhost:6379/0',
             backend='redis://localhost:6379/0')

app.conf.timezone = 'UTC'
app.conf.broker_connection_retry_on_startup = True

# Schedule weekly run - Monday 9 AM
app.conf.beat_schedule = {
    'generate-leads-weekly': {
        'task': 'scheduler.generate_all_leads',
        'schedule': crontab(day_of_week=1, hour=9, minute=0),
    },
}

@app.task
def generate_all_leads():
    """Generate leads for all cities and clinic types"""
    from etl import run_pipeline
    from google_sheets import export_to_sheets
    
    results = []
    
    # Run for all countries
    for country, cities in CITIES.items():
        for city in cities:
            for clinic_type in CLINIC_TYPES:
                try:
                    result = run_pipeline(city, clinic_type)
                    results.append(result)
                    print(f"Done: {city} - {clinic_type}: {result['total_added']} added")
                except Exception as e:
                    print(f"Error: {city} - {clinic_type}: {e}")
    
    # Export to Google Sheets
    export_to_sheets()
    
    return {
        "total_runs": len(results),
        "results": results
    }

@app.task
def generate_specific_city(city, clinic_type):
    """Generate leads for specific city and clinic type"""
    from etl import run_pipeline
    from google_sheets import export_to_sheets
    
    result = run_pipeline(city, clinic_type)
    export_to_sheets()
    
    return result

def run_manual():
    """Manual trigger for testing"""
    print("Running manual lead generation...")
    result = generate_all_leads()
    print(f"Manual run completed: {result}")
    return result

if __name__ == "__main__":
    # For testing without Celery
    print("Run with: celery -A scheduler worker --beat --loglevel=info")