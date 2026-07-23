from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()

class Lead(Base):
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Basic Info
    clinic_name = Column(String(200), nullable=False)
    clinic_type = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    address = Column(String(500))
    
    # Contact Info
    phone_number = Column(String(50))
    email = Column(String(200))
    website_url = Column(String(500))
    
    # Doctor & Social
    doctor_name = Column(String(200))
    social_links = Column(String(500))  # JSON string
    
    # Appointment & Automation
    appointment_method = Column(String(100))
    automation_status = Column(String(50))
    
    # Ratings & Priority
    google_rating = Column(String(10))
    reviews_count = Column(Integer, default=0)
    lead_priority = Column(String(20), default="Medium")
    
    # Internal
    notes = Column(String(500))
    call_status = Column(String(50), default="New")
    follow_up_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "Lead ID": self.id,
            "Clinic Name": self.clinic_name,
            "Clinic Type": self.clinic_type,
            "Country": self.country,
            "City": self.city,
            "Address": self.address,
            "Appointment Method": self.appointment_method,
            "Phone Number": self.phone_number,
            "Email": self.email,
            "Website Available": "Yes" if self.website_url else "No",
            "Website URL": self.website_url,
            "Doctor/Owner Name": self.doctor_name,
            "Social Media Links": self.social_links,
            "Automation Status": self.automation_status,
            "Google Rating": self.google_rating,
            "Reviews Count": self.reviews_count,
            "Lead Priority": self.lead_priority,
            "Notes": self.notes,
            "Call Status": self.call_status,
            "Follow-up Date": str(self.follow_up_date) if self.follow_up_date else ""
        }

# Database setup
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)