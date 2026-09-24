import json
import logging
from datetime import datetime, date, timedelta
from app.extensions import db
from app.models.patient import Patient
from app.models.wearable import HealthMetric, DailyHealthSummary
from app.models.daily_log import DailyHealthLog
from app.services.bmi_service import calculate_bmi

logger = logging.getLogger(__name__)

def aggregate_daily_health_summary(patient_id: str, start_date: date, end_date: date):
    """
    Aggregates daily HealthMetrics and manual DailyHealthLogs into normalized DailyHealthSummary rows.
    Also syncs smart scale weight updates back to the Patient profile.
    """
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return
        
    current_date = start_date
    while current_date <= end_date:
        next_day = current_date + timedelta(days=1)
        
        # 1. Fetch metrics logged on this day
        metrics = HealthMetric.query.filter(
            HealthMetric.patient_id == patient_id,
            HealthMetric.timestamp >= datetime.combine(current_date, datetime.min.time()),
            HealthMetric.timestamp < datetime.combine(next_day, datetime.min.time())
        ).all()
        
        # 2. Fetch manual check-in log on this day
        manual_log = DailyHealthLog.query.filter_by(
            patient_id=patient_id,
            log_date=current_date
        ).first()
        
        # Aggregate variables
        total_steps = None
        calories_burned = None
        active_minutes = None
        average_heart_rate = None
        resting_heart_rate = None
        sleep_hours = None
        weight = None
        systolic_bp = None
        diastolic_bp = None
        blood_glucose = None
        spo2 = None
        
        sources = {}
        
        # Parse metrics
        for m in metrics:
            if m.metric_type == 'steps':
                total_steps = int(m.value)
                sources['steps'] = m.source
            elif m.metric_type == 'calories':
                calories_burned = m.value
                sources['calories'] = m.source
            elif m.metric_type == 'active_minutes':
                active_minutes = int(m.value)
                sources['active_minutes'] = m.source
            elif m.metric_type == 'heart_rate':
                average_heart_rate = m.value
                sources['heart_rate'] = m.source
            elif m.metric_type == 'resting_heart_rate':
                resting_heart_rate = int(m.value)
                sources['resting_heart_rate'] = m.source
            elif m.metric_type == 'sleep':
                sleep_hours = m.value
                sources['sleep'] = m.source
            elif m.metric_type == 'weight':
                weight = m.value
                sources['weight'] = m.source
            elif m.metric_type == 'blood_pressure_systolic':
                systolic_bp = int(m.value)
                sources['blood_pressure_systolic'] = m.source
            elif m.metric_type == 'blood_pressure_diastolic':
                diastolic_bp = int(m.value)
                sources['blood_pressure_diastolic'] = m.source
            elif m.metric_type == 'blood_glucose':
                blood_glucose = m.value
                sources['blood_glucose'] = m.source
            elif m.metric_type == 'spo2':
                spo2 = m.value
                sources['spo2'] = m.source
                
        # Merge manual check-in log if wearable data is missing
        if manual_log:
            if total_steps is None and manual_log.exercise_duration is not None:
                # Approximate steps: 120 steps per exercise minute as a rough backup
                total_steps = manual_log.exercise_duration * 120
                sources['steps'] = 'manual'
            if sleep_hours is None and manual_log.sleep_hours is not None:
                sleep_hours = manual_log.sleep_hours
                sources['sleep'] = 'manual'
            if weight is None and manual_log.weight is not None:
                weight = manual_log.weight
                sources['weight'] = 'manual'
            if systolic_bp is None and manual_log.systolic_bp is not None:
                systolic_bp = manual_log.systolic_bp
                sources['blood_pressure_systolic'] = 'manual'
            if diastolic_bp is None and manual_log.diastolic_bp is not None:
                diastolic_bp = manual_log.diastolic_bp
                sources['blood_pressure_diastolic'] = 'manual'
            if blood_glucose is None and manual_log.blood_glucose is not None:
                blood_glucose = manual_log.blood_glucose
                sources['blood_glucose'] = 'manual'
                
        # 3. Save weight baseline update to Patient profile if scale value is new and latest
        if weight is not None and current_date == date.today():
            patient.weight = weight
            patient.bmi = calculate_bmi(weight, patient.height)
            
        # 4. Save or update summary
        summary = DailyHealthSummary.query.filter_by(
            patient_id=patient_id,
            date=current_date
        ).first()
        
        if not summary:
            summary = DailyHealthSummary(
                patient_id=patient_id,
                date=current_date,
                total_steps=total_steps,
                calories_burned=calories_burned,
                active_minutes=active_minutes,
                average_heart_rate=average_heart_rate,
                resting_heart_rate=resting_heart_rate,
                sleep_hours=sleep_hours,
                weight=weight,
                systolic_bp=systolic_bp,
                diastolic_bp=diastolic_bp,
                blood_glucose=blood_glucose,
                spo2=spo2,
                data_sources=json.dumps(sources),
                generated_at=datetime.utcnow()
            )
            db.session.add(summary)
        else:
            summary.total_steps = total_steps
            summary.calories_burned = calories_burned
            summary.active_minutes = active_minutes
            summary.average_heart_rate = average_heart_rate
            summary.resting_heart_rate = resting_heart_rate
            summary.sleep_hours = sleep_hours
            summary.weight = weight
            summary.systolic_bp = systolic_bp
            summary.diastolic_bp = diastolic_bp
            summary.blood_glucose = blood_glucose
            summary.spo2 = spo2
            summary.data_sources = json.dumps(sources)
            summary.generated_at = datetime.utcnow()
            
        db.session.commit()
        current_date += timedelta(days=1)
