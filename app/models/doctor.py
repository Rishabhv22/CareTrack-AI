import uuid
from datetime import datetime
from app.extensions import db

# Association Table for Patient-Doctor relationships
patient_doctor_association = db.Table('patient_doctor_relationships',
    db.Column('id', db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    db.Column('patient_id', db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
    db.Column('doctor_id', db.String(36), db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

class Doctor(db.Model):
    __tablename__ = 'doctors'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    clinic_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='doctor_profile')
    
    # Patients many-to-many relationship
    patients = db.relationship('Patient', 
                               secondary=patient_doctor_association,
                               back_populates='doctors')
                               
    notes = db.relationship('DoctorNote', back_populates='doctor', cascade="all, delete-orphan")
    prescriptions = db.relationship('Medication', back_populates='prescribed_by', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Doctor {self.name} - {self.clinic_name}>'
