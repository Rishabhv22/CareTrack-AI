import uuid
from datetime import datetime
from app.extensions import db
from app.utils.encryption import EncryptedText

class DailyHealthLog(db.Model):
    __tablename__ = 'daily_health_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    log_date = db.Column(db.Date, nullable=False, index=True)
    
    # Measurements
    weight = db.Column(db.Float, nullable=True)  # in kg
    water_intake = db.Column(db.Float, nullable=True)  # in L or mL
    calories = db.Column(db.Integer, nullable=True)
    exercise_duration = db.Column(db.Integer, nullable=True)  # in minutes
    sleep_hours = db.Column(db.Float, nullable=True)
    
    # Bio-markers
    blood_glucose = db.Column(db.Float, nullable=True)  # mg/dL
    systolic_bp = db.Column(db.Integer, nullable=True)  # mmHg
    diastolic_bp = db.Column(db.Integer, nullable=True)  # mmHg
    
    # Compliance check-ins
    medicine_taken = db.Column(db.Boolean, default=False)
    exercise_completed = db.Column(db.Boolean, default=False)
    diet_followed = db.Column(db.Boolean, default=False)
    
    # State of mind
    mood = db.Column(db.String(20), nullable=True)  # 'Good', 'Neutral', 'Low'
    energy = db.Column(db.String(20), nullable=True)  # 'High', 'Medium', 'Low'
    symptoms = db.Column(EncryptedText, nullable=True)  # Free text symptoms
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='daily_logs')
    journal_entry = db.relationship('JournalEntry', back_populates='daily_log', uselist=False, cascade="all, delete-orphan")
    
    # Unique constraint on patient and log_date
    __table_args__ = (db.UniqueConstraint('patient_id', 'log_date', name='_patient_date_uc'),)
    
    def __repr__(self):
        return f'<DailyHealthLog date={self.log_date} patient={self.patient_id}>'
