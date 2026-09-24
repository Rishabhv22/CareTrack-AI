import uuid
from datetime import datetime
from app.extensions import db

class WearableDevice(db.Model):
    __tablename__ = 'wearable_devices'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    
    provider = db.Column(db.String(50), nullable=False)  # e.g., 'Fitbit', 'Garmin', 'Apple Health', 'Health Connect', 'Demo Wearable'
    device_name = db.Column(db.String(100), nullable=False)  # e.g., 'Inspire 3', 'Fenix 7'
    device_type = db.Column(db.String(50), nullable=False)  # e.g., 'Smartwatch', 'Fitness Tracker', 'Scale'
    external_device_id = db.Column(db.String(100), nullable=True)
    
    connection_status = db.Column(db.String(20), default='CONNECTED', nullable=False)  # 'CONNECTED', 'DISCONNECTED'
    connected_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    
    # Credentials (tokens)
    access_token = db.Column(db.String(512), nullable=True)
    refresh_token = db.Column(db.String(512), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='wearable_devices')
    health_metrics = db.relationship('HealthMetric', back_populates='device', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<WearableDevice {self.provider} - {self.device_name} for Patient {self.patient_id}>'


class HealthMetric(db.Model):
    __tablename__ = 'health_metrics'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    device_id = db.Column(db.String(36), db.ForeignKey('wearable_devices.id', ondelete='SET NULL'), nullable=True)
    
    metric_type = db.Column(db.String(50), nullable=False, index=True)  # 'steps', 'sleep', 'heart_rate', 'resting_heart_rate', 'weight', 'blood_pressure_systolic', 'blood_pressure_diastolic', 'blood_glucose', 'spo2', 'active_minutes', 'calories'
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    source = db.Column(db.String(50), nullable=False)  # 'manual', 'wearable', 'health_platform', 'medical_device', 'medical_report'
    
    external_record_id = db.Column(db.String(100), nullable=True)
    confidence = db.Column(db.Float, default=1.0)  # Data quality rating: 1.0 = High, 0.5 = Low/Questionable, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='health_metrics')
    device = db.relationship('WearableDevice', back_populates='health_metrics')
    
    # Prevent duplicate metrics for the exact same patient, metric type, and timestamp
    __table_args__ = (
        db.UniqueConstraint('patient_id', 'metric_type', 'timestamp', name='_patient_metric_timestamp_uc'),
    )
    
    def __repr__(self):
        return f'<HealthMetric {self.metric_type}: {self.value} {self.unit} source={self.source}>'


class DailyHealthSummary(db.Model):
    __tablename__ = 'daily_health_summaries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    
    total_steps = db.Column(db.Integer, nullable=True)
    calories_burned = db.Column(db.Float, nullable=True)
    active_minutes = db.Column(db.Integer, nullable=True)
    average_heart_rate = db.Column(db.Float, nullable=True)
    resting_heart_rate = db.Column(db.Integer, nullable=True)
    sleep_hours = db.Column(db.Float, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    
    systolic_bp = db.Column(db.Integer, nullable=True)
    diastolic_bp = db.Column(db.Integer, nullable=True)
    blood_glucose = db.Column(db.Float, nullable=True)
    spo2 = db.Column(db.Float, nullable=True)
    
    data_sources = db.Column(db.Text, nullable=True)  # JSON-encoded dictionary: {metric_type: source}
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='daily_health_summaries')
    
    # Prevent duplicate summaries for the same patient and day
    __table_args__ = (
        db.UniqueConstraint('patient_id', 'date', name='_patient_date_summary_uc'),
    )
    
    def __repr__(self):
        return f'<DailyHealthSummary patient={self.patient_id} date={self.date} steps={self.total_steps}>'
