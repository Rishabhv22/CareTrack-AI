import uuid
from datetime import datetime
from app.extensions import db
from app.utils.encryption import EncryptedText

class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    daily_log_id = db.Column(db.String(36), db.ForeignKey('daily_health_logs.id', ondelete='CASCADE'), nullable=True)
    
    entry_date = db.Column(db.Date, nullable=False, index=True)
    journal_text = db.Column(EncryptedText, nullable=False)
    
    # NLP extraction results
    summary = db.Column(db.Text, nullable=True)
    extracted_symptoms = db.Column(db.Text, nullable=True)  # Store as comma-separated or JSON list
    extracted_medications = db.Column(db.Text, nullable=True)  # Actions like taken, missed
    extracted_diet_activity = db.Column(db.Text, nullable=True)
    
    concerning_flag = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    daily_log = db.relationship('DailyHealthLog', back_populates='journal_entry')
    
    def __repr__(self):
        return f'<JournalEntry date={self.entry_date} patient={self.patient_id}>'
