from datetime import datetime, timedelta
from app.models.daily_log import DailyHealthLog
from app.models.medication import Medication, MedicationLog
from app.models.medical_report import MedicalReport

def calculate_adherence_score(patient, days=30):
    """
    Calculates the 'Care Adherence Score' (0-100) for a patient.
    Weights:
      - Medication Adherence: 40%
      - Exercise Consistency: 20%
      - Diet Compliance: 20%
      - Daily Logging Frequency: 10%
      - Report Upload Compliance: 10%
    """
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days)
    
    # 1. Daily Logging Frequency (10 points)
    # Count logs in the lookback window
    logs = DailyHealthLog.query.filter(
        DailyHealthLog.patient_id == patient.id,
        DailyHealthLog.log_date >= start_date
    ).all()
    log_count = len(logs)
    log_score = (log_count / days) * 10.0
    log_score = min(10.0, max(0.0, log_score))
    
    # 2. Medication Adherence (40 points)
    meds = Medication.query.filter_by(patient_id=patient.id, is_active=True).all()
    if not meds:
        # If no medication is prescribed, patient gets full points for this section
        med_score = 40.0
        med_ratio = 1.0
    else:
        # Calculate overall ratio of TAKEN logs
        total_active_days = 0
        total_taken = 0
        for med in meds:
            # Calculate intersection of prescription dates and lookback window
            pres_start = max(med.start_date, start_date)
            pres_end = today
            if med.end_date:
                pres_end = min(med.end_date, today)
                
            active_days = (pres_end - pres_start).days + 1
            if active_days <= 0:
                continue
                
            taken_logs = MedicationLog.query.filter(
                MedicationLog.medication_id == med.id,
                MedicationLog.log_date >= pres_start,
                MedicationLog.log_date <= pres_end,
                MedicationLog.status == 'TAKEN'
            ).count()
            
            total_active_days += active_days
            total_taken += taken_logs
            
        if total_active_days > 0:
            med_ratio = total_taken / total_active_days
            med_score = med_ratio * 40.0
        else:
            med_ratio = 1.0
            med_score = 40.0
            
    # 3. Exercise Consistency (20 points)
    # Target: 4 exercise sessions per week (approx 60% of logged days)
    # If the patient has connected wearables: we can check their aggregated DailyHealthSummary records.
    # If summary.active_minutes >= 30 or summary.total_steps >= 7000, we count that day as active.
    from app.models.wearable import DailyHealthSummary
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient.id,
        DailyHealthSummary.date >= start_date
    ).all()
    
    active_days_set = set()
    for log in logs:
        if log.exercise_completed:
            active_days_set.add(log.log_date)
            
    for summary in summaries:
        if (summary.active_minutes and summary.active_minutes >= 30) or (summary.total_steps and summary.total_steps >= 7000):
            active_days_set.add(summary.date)
            
    exercise_days = len(active_days_set)
    total_tracked_days = max(log_count, len(summaries), 1)
    
    exercise_ratio = exercise_days / total_tracked_days
    exercise_score = exercise_ratio * 20.0
    exercise_score = min(20.0, max(0.0, exercise_score))
        
    # 4. Diet Compliance (20 points)
    diet_days = sum(1 for log in logs if log.diet_followed)
    if log_count > 0:
        diet_ratio = diet_days / log_count
        diet_score = diet_ratio * 20.0
    else:
        diet_ratio = 0.0
        diet_score = 0.0
        
    # 5. Follow-up / Report Upload Compliance (10 points)
    # Check if a report has been uploaded in the last 90 days
    recent_reports_count = MedicalReport.query.filter(
        MedicalReport.patient_id == patient.id,
        MedicalReport.uploaded_at >= (datetime.utcnow() - timedelta(days=90))
    ).count()
    report_score = 10.0 if recent_reports_count > 0 else 0.0
    
    # Calculate total
    total_score = round(log_score + med_score + exercise_score + diet_score + report_score)
    
    return {
        'total': total_score,
        'logging': {
            'score': round(log_score, 1),
            'ratio': log_count / days,
            'count': log_count,
            'max': 10
        },
        'medication': {
            'score': round(med_score, 1),
            'ratio': med_ratio,
            'max': 40
        },
        'exercise': {
            'score': round(exercise_score, 1),
            'ratio': exercise_ratio,
            'count': exercise_days,
            'max': 20
        },
        'diet': {
            'score': round(diet_score, 1),
            'ratio': diet_ratio,
            'count': diet_days,
            'max': 20
        },
        'report': {
            'score': round(report_score, 1),
            'has_report': recent_reports_count > 0,
            'max': 10
        }
    }
