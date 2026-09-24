import uuid
from datetime import datetime
from app.extensions import db
from app.utils.encryption import EncryptedText

class Recommendation(db.Model):
    __tablename__ = 'recommendations'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.String(36), db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    
    recommendation_text = db.Column(db.Text, nullable=False)  # Lifestyle advice, exercise suggestions
    category = db.Column(db.String(50), nullable=True)  # 'Nutrition', 'Exercise', 'General'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Recommendation to Patient {self.patient_id} by Doctor {self.doctor_id}>'

class DoctorNote(db.Model):
    __tablename__ = 'doctor_notes'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.String(36), db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    
    note_text = db.Column(EncryptedText, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='doctor_notes')
    doctor = db.relationship('Doctor', back_populates='notes')
    
    def __repr__(self):
        return f'<DoctorNote for Patient {self.patient_id} by Doctor {self.doctor_id}>'

class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    
    alert_type = db.Column(db.String(50), nullable=False)  # 'Compliance', 'Symptom', 'Biometric', 'Missing Data'
    severity = db.Column(db.String(20), nullable=False)  # 'LOW', 'MEDIUM', 'HIGH'
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='ACTIVE')  # 'ACTIVE', 'RESOLVED'
    
    resolved_by_id = db.Column(db.String(36), db.ForeignKey('doctors.id', ondelete='SET NULL'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='alerts')
    
    def __repr__(self):
        return f'<Alert {self.alert_type} {self.severity} for Patient {self.patient_id}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='notifications')
    
    def __repr__(self):
        return f'<Notification user={self.user_id} title={self.title} read={self.is_read}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True)
    
    action = db.Column(db.String(100), nullable=False)  # e.g., 'LOGIN', 'REPORT_UPLOAD', 'PRESCRIPTION_CHANGE'
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='audit_logs')
    patient = db.relationship('Patient')
    
    def __repr__(self):
        return f'<AuditLog user={self.user_id} patient={self.patient_id} action={self.action}>'

class ClinicalInsight(db.Model):
    __tablename__ = 'clinical_insights'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    
    insight_type = db.Column(db.String(50), nullable=False)  # 'AdherenceTrend', 'WeightTrend', 'GlucoseTrend', 'SymptomFrequency'
    insight_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='clinical_insights')
    
    def __repr__(self):
        return f'<ClinicalInsight for Patient {self.patient_id}>'

class AISummary(db.Model):
    __tablename__ = 'ai_summaries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    
    summary_text = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_acknowledged = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='ai_summaries')
    
    def __repr__(self):
        return f'<AISummary Patient {self.patient_id} from {self.start_date} to {self.end_date}>'
