import logging
from app.extensions import db
from app.models.wearable import HealthMetric
from app.models.recommendation import Alert

logger = logging.getLogger(__name__)

def validate_and_flag_metric(patient_id: str, metric_type: str, value: float, timestamp) -> dict:
    """
    Validates a health metric entry. Enforces range limits, flags questionable readings
    by adjusting data confidence/quality, and raises clinical alerts for clinicians when appropriate.
    Returns a dict with 'confidence' (float) and 'raise_alert' (bool, message, severity).
    """
    confidence = 1.0
    alert_info = {'raise': False, 'message': '', 'severity': 'MEDIUM'}
    
    # 1. Validation bounds
    if metric_type == 'steps':
        if value < 0:
            raise ValueError("Steps cannot be negative.")
        if value > 50000:
            confidence = 0.5  # Technical sensor/accelerometer glitch
            
    elif metric_type == 'calories':
        if value < 0:
            raise ValueError("Calories burned cannot be negative.")
        if value > 10000:
            confidence = 0.5
            
    elif metric_type == 'sleep':
        if value < 0.0 or value > 24.0:
            raise ValueError("Sleep hours must be between 0 and 24.")
        if value > 18.0 or (0.0 < value < 3.0):
            confidence = 0.8
            
    elif metric_type == 'heart_rate':
        if value < 30.0 or value > 220.0:
            raise ValueError("Heart rate must be within range [30, 220] BPM.")
        if value > 160.0:
            confidence = 0.7
            alert_info = {
                'raise': True,
                'message': f"Elevated average heart rate detected: {int(value)} BPM. Clinician review advised.",
                'severity': 'MEDIUM'
            }
            
    elif metric_type == 'resting_heart_rate':
        if value < 30.0 or value > 180.0:
            raise ValueError("Resting heart rate must be within range [30, 180] BPM.")
        if value < 40.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Resting bradycardia reading flagged: {int(value)} BPM. Discuss with clinician.",
                'severity': 'MEDIUM'
            }
        elif value > 100.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Resting tachycardia reading flagged: {int(value)} BPM. Discuss with clinician.",
                'severity': 'MEDIUM'
            }
            
    elif metric_type == 'weight':
        if value <= 2.0 or value > 600.0:
            raise ValueError("Weight must be positive and within reasonable physiological bounds.")
            
    elif metric_type == 'blood_pressure_systolic':
        if value < 40.0 or value > 300.0:
            raise ValueError("Systolic blood pressure must be within [40, 300] mmHg.")
        if value > 180.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Severe hypertensive range reading: {int(value)} mmHg systolic. Patient advised to rest and contact provider.",
                'severity': 'HIGH'
            }
        elif value < 80.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Low blood pressure range reading: {int(value)} mmHg systolic. Clinician overview advised.",
                'severity': 'MEDIUM'
            }
            
    elif metric_type == 'blood_pressure_diastolic':
        if value < 30.0 or value > 200.0:
            raise ValueError("Diastolic blood pressure must be within [30, 200] mmHg.")
        if value > 110.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Severe hypertensive range reading: {int(value)} mmHg diastolic. Clinician overview advised.",
                'severity': 'HIGH'
            }
        elif value < 45.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Low blood pressure range reading: {int(value)} mmHg diastolic. Clinician overview advised.",
                'severity': 'MEDIUM'
            }
            
    elif metric_type == 'blood_glucose':
        if value < 10.0 or value > 1000.0:
            raise ValueError("Blood glucose must be within range [10, 1000] mg/dL.")
        if value < 55.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Hypoglycemia observation: {value} mg/dL. Prompt clinical check suggested.",
                'severity': 'HIGH'
            }
        elif value > 280.0:
            confidence = 0.9
            alert_info = {
                'raise': True,
                'message': f"Hyperglycemia observation: {value} mg/dL. Monitor levels alongside medication compliance.",
                'severity': 'HIGH'
            }
            
    elif metric_type == 'spo2':
        if value < 0.0 or value > 100.0:
            raise ValueError("SpO2 percentage must be between 0 and 100.")
        if value < 90.0:
            confidence = 0.8
            alert_info = {
                'raise': True,
                'message': f"Hypoxia alert: Device-reported SpO2 blood oxygen level fell to {value}%. Clinician review required.",
                'severity': 'HIGH'
            }
            
    return {
        'confidence': confidence,
        'alert_info': alert_info
    }


def add_health_metric(patient_id: str, device_id: str, metric_type: str, value: float, unit: str, timestamp, source: str, external_record_id: str = None) -> HealthMetric:
    """
    Validates, flags, and saves a health metric record in the database.
    Triggers clinical alert models if critical deviations are detected.
    """
    # 1. Run validation
    validation = validate_and_flag_metric(patient_id, metric_type, value, timestamp)
    
    # 2. Check for duplicate logs (patient_id + metric_type + timestamp unique constraint)
    existing = HealthMetric.query.filter_by(
        patient_id=patient_id,
        metric_type=metric_type,
        timestamp=timestamp
    ).first()
    
    if existing:
        logger.info(f"Duplicate metric ignored for patient {patient_id}, type {metric_type}, time {timestamp}")
        return existing

    metric = HealthMetric(
        patient_id=patient_id,
        device_id=device_id,
        metric_type=metric_type,
        value=value,
        unit=unit,
        timestamp=timestamp,
        source=source,
        external_record_id=external_record_id,
        confidence=validation['confidence']
    )
    db.session.add(metric)
    
    # 3. Create active alert if validation flags a critical value
    alert_data = validation['alert_info']
    if alert_data['raise']:
        # Ensure we don't spam identical active alerts for the same patient
        existing_alert = Alert.query.filter_by(
            patient_id=patient_id,
            alert_type='Biometric',
            message=alert_data['message'],
            status='ACTIVE'
        ).first()
        
        if not existing_alert:
            alert = Alert(
                patient_id=patient_id,
                alert_type='Biometric',
                severity=alert_data['severity'],
                message=alert_data['message'],
                status='ACTIVE'
            )
            db.session.add(alert)
            
    return metric
