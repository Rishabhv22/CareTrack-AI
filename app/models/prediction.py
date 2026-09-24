import uuid
from datetime import datetime
from app.extensions import db

class Prediction(db.Model):
    __tablename__ = 'predictions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    
    model_name = db.Column(db.String(50), nullable=False)  # 'Random Forest', 'Logistic Regression', 'K-Means Clustering'
    prediction_result = db.Column(db.String(100), nullable=False)  # 'Improving', 'Stable', 'Deteriorating'
    features_used = db.Column(db.Text, nullable=True)  # Store features JSON
    confidence_score = db.Column(db.Float, nullable=True)  # Probability for classifiers
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='predictions')
    
    def __repr__(self):
        return f'<Prediction patient={self.patient_id} result={self.prediction_result}>'
