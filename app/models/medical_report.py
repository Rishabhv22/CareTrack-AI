import uuid
from datetime import datetime
from app.extensions import db

class MedicalReport(db.Model):
    __tablename__ = 'medical_reports'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    uploaded_by_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_processed = db.Column(db.Boolean, default=False)
    raw_text = db.Column(db.Text, nullable=True)  # Extracted OCR text
    
    # Relationships
    patient = db.relationship('Patient', back_populates='medical_reports')
    lab_results = db.relationship('LabResult', back_populates='report', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<MedicalReport {self.file_name} for Patient {self.patient_id}>'

class LabResult(db.Model):
    __tablename__ = 'lab_results'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = db.Column(db.String(36), db.ForeignKey('medical_reports.id', ondelete='CASCADE'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    
    parameter_name = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'HbA1c', 'Glucose', 'Total Cholesterol'
    parameter_value = db.Column(db.Float, nullable=False)
    normal_range = db.Column(db.String(50), nullable=True)  # e.g., '4.0 - 5.6'
    unit = db.Column(db.String(20), nullable=True)  # e.g., '%', 'mg/dL'
    test_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    confidence = db.Column(db.Float, nullable=True)  # Extraction confidence percentage (0.0 to 1.0)
    
    # Relationships
    report = db.relationship('MedicalReport', back_populates='lab_results')
    
    def __repr__(self):
        return f'<LabResult {self.parameter_name}: {self.parameter_value} {self.unit}>'
