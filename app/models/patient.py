import uuid
from datetime import datetime
from app.extensions import db
from app.models.doctor import patient_doctor_association
from app.utils.encryption import EncryptedText

class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    
    # Demographics/Health profile
    height = db.Column(db.Float, nullable=False)  # in cm
    weight = db.Column(db.Float, nullable=False)  # in kg
    bmi = db.Column(db.Float, nullable=True)
    
    primary_condition = db.Column(db.String(100), nullable=False)  # e.g., 'Type 2 Diabetes', 'Hypertension'
    other_conditions = db.Column(EncryptedText, nullable=True)  # Comorbidities
    allergies = db.Column(EncryptedText, nullable=True)
    family_history = db.Column(EncryptedText, nullable=True)
    
    # Lifestyle choices
    smoking = db.Column(db.String(20), nullable=True)  # 'Never', 'Former', 'Active'
    alcohol = db.Column(db.String(20), nullable=True)  # 'None', 'Occasional', 'Regular'
    sleep_hours = db.Column(db.Float, default=7.0)
    activity_level = db.Column(db.String(30), default='Moderate')  # 'Sedentary', 'Light', 'Moderate', 'Active'
    
    # Wearable Consent
    health_data_consent = db.Column(db.Boolean, default=False, nullable=False)
    ml_acknowledged = db.Column(db.Boolean, default=False, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='patient_profile')
    
    doctors = db.relationship('Doctor', 
                              secondary=patient_doctor_association,
                              back_populates='patients')
                              
    daily_logs = db.relationship('DailyHealthLog', back_populates='patient', cascade="all, delete-orphan", order_by="desc(DailyHealthLog.log_date)")
    medical_reports = db.relationship('MedicalReport', back_populates='patient', cascade="all, delete-orphan")
    medications = db.relationship('Medication', back_populates='patient', cascade="all, delete-orphan")
    medication_logs = db.relationship('MedicationLog', back_populates='patient', cascade="all, delete-orphan")
    alerts = db.relationship('Alert', back_populates='patient', cascade="all, delete-orphan")
    doctor_notes = db.relationship('DoctorNote', back_populates='patient', cascade="all, delete-orphan")
    clinical_insights = db.relationship('ClinicalInsight', back_populates='patient', cascade="all, delete-orphan")
    ai_summaries = db.relationship('AISummary', back_populates='patient', cascade="all, delete-orphan")
    predictions = db.relationship('Prediction', back_populates='patient', cascade="all, delete-orphan")
    
    # Wearable & Health Data Relationships
    wearable_devices = db.relationship('WearableDevice', back_populates='patient', cascade="all, delete-orphan")
    health_metrics = db.relationship('HealthMetric', back_populates='patient', cascade="all, delete-orphan")
    daily_health_summaries = db.relationship('DailyHealthSummary', back_populates='patient', cascade="all, delete-orphan", order_by="desc(DailyHealthSummary.date)")

    def __repr__(self):
        return f'<Patient {self.name} - {self.primary_condition}>'
