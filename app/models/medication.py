import uuid
from datetime import datetime
from app.extensions import db

class Medication(db.Model):
    __tablename__ = 'medications'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    prescribed_by_id = db.Column(db.String(36), db.ForeignKey('doctors.id', ondelete='SET NULL'), nullable=True)
    
    name = db.Column(db.String(100), nullable=False)  # e.g., 'Metformin'
    dosage = db.Column(db.String(50), nullable=False)  # e.g., '500mg'
    frequency = db.Column(db.String(50), nullable=False)  # e.g., 'Twice daily'
    timing = db.Column(db.String(50), nullable=True)  # e.g., 'After meals'
    instructions = db.Column(db.Text, nullable=True)  # e.g., 'Take with plenty of water'
    
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    end_date = db.Column(db.Date, nullable=True)  # Open-ended if NULL
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='medications')
    prescribed_by = db.relationship('Doctor', back_populates='prescriptions')
    logs = db.relationship('MedicationLog', back_populates='medication', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Medication {self.name} {self.dosage} for Patient {self.patient_id}>'

class MedicationLog(db.Model):
    __tablename__ = 'medication_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    medication_id = db.Column(db.String(36), db.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False)
    
    log_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='TAKEN')  # 'TAKEN', 'MISSED', 'SKIPPED'
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='medication_logs')
    medication = db.relationship('Medication', back_populates='logs')
    
    def __repr__(self):
        return f'<MedicationLog date={self.log_date} status={self.status} med={self.medication_id}>'
