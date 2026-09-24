from datetime import datetime, timedelta, date
from app.extensions import db
from app.models.daily_log import DailyHealthLog
from app.models.recommendation import ClinicalInsight, Alert
from app.models.wearable import DailyHealthSummary, WearableDevice
from app.services.compliance_engine import calculate_adherence_score

def run_insight_engine(patient):
    """
    Analyzes historical daily logs, report values, compliance logs,
    and automatic wearable summaries to extract clinical insights and trigger alerts.
    """
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=30)
    
    # Clear existing insights to update with fresh calculations
    ClinicalInsight.query.filter_by(patient_id=patient.id).delete()
    
    # Retrieve logs and summaries in chronological order
    logs = DailyHealthLog.query.filter(
        DailyHealthLog.patient_id == patient.id,
        DailyHealthLog.log_date >= start_date
    ).order_by(DailyHealthLog.log_date.asc()).all()
    
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient.id,
        DailyHealthSummary.date >= start_date
    ).order_by(DailyHealthSummary.date.asc()).all()
    
    log_count = len(logs)
    summary_count = len(summaries)
    
    if log_count < 4 and summary_count < 4:
        # Not enough data points to compute trends
        db.session.add(ClinicalInsight(
            patient_id=patient.id,
            insight_type='System',
            insight_text='Collecting baseline health data. Insights will trigger after logging 4 or more check-ins/syncs.'
        ))
        db.session.commit()
        return
        
    # Split logs/summaries into halves (First 15 days vs Last 15 days of window)
    mid_point = start_date + timedelta(days=15)
    first_half_logs = [l for l in logs if l.log_date < mid_point]
    second_half_logs = [l for l in logs if l.log_date >= mid_point]
    
    first_half_sums = [s for s in summaries if s.date < mid_point]
    second_half_sums = [s for s in summaries if s.date >= mid_point]
    
    # 1. Weight Change Trend (Combine summaries and logs)
    first_weights = [s.weight for s in first_half_sums if s.weight is not None] or [l.weight for l in first_half_logs if l.weight is not None]
    second_weights = [s.weight for s in second_half_sums if s.weight is not None] or [l.weight for l in second_half_logs if l.weight is not None]
    
    if first_weights and second_weights:
        avg_w1 = sum(first_weights) / len(first_weights)
        avg_w2 = sum(second_weights) / len(second_weights)
        weight_diff = round(avg_w2 - avg_w1, 1)
        
        if abs(weight_diff) >= 0.5:
            direction = "decreased" if weight_diff < 0 else "increased"
            db.session.add(ClinicalInsight(
                patient_id=patient.id,
                insight_type='WeightTrend',
                insight_text=f"Average body weight {direction} by {abs(weight_diff)} kg over the last 30 days."
            ))
            
    # 2. Blood Glucose Trend (Combine summaries and logs)
    first_glucose = [s.blood_glucose for s in first_half_sums if s.blood_glucose is not None] or [l.blood_glucose for l in first_half_logs if l.blood_glucose is not None]
    second_glucose = [s.blood_glucose for s in second_half_sums if s.blood_glucose is not None] or [l.blood_glucose for l in second_half_logs if l.blood_glucose is not None]
    
    if first_glucose and second_glucose:
        avg_g1 = sum(first_glucose) / len(first_glucose)
        avg_g2 = sum(second_glucose) / len(second_glucose)
        glucose_diff = round(avg_g2 - avg_g1, 1)
        
        if abs(glucose_diff) >= 10:
            direction = "decreased" if glucose_diff < 0 else "increased"
            db.session.add(ClinicalInsight(
                patient_id=patient.id,
                insight_type='GlucoseTrend',
                insight_text=f"Average fasting blood glucose level {direction} by {abs(glucose_diff)} mg/dL compared to the first half of the month."
            ))

    # 3. Exercise consistency change
    first_ex_ratio = sum(1 for l in first_half_logs if l.exercise_completed) / max(1, len(first_half_logs))
    second_ex_ratio = sum(1 for l in second_half_logs if l.exercise_completed) / max(1, len(second_half_logs))
    
    first_ex_days = round(first_ex_ratio * 7)
    second_ex_days = round(second_ex_ratio * 7)
    
    if first_ex_days != second_ex_days:
        direction = "increased" if second_ex_days > first_ex_days else "decreased"
        db.session.add(ClinicalInsight(
            patient_id=patient.id,
            insight_type='ExerciseTrend',
            insight_text=f"Exercise consistency {direction} from {first_ex_days} days/week to {second_ex_days} days/week."
        ))

    # 4. Check for logging gaps (Manual logs)
    if logs:
        latest_log = logs[-1]
        days_since_last_log = (today - latest_log.log_date).days
        if days_since_last_log >= 4:
            db.session.add(ClinicalInsight(
                patient_id=patient.id,
                insight_type='ComplianceGap',
                insight_text=f"Patient has missed daily check-in logs for {days_since_last_log} consecutive days."
            ))
            
            # Raise alert if not already active
            existing_gap_alert = Alert.query.filter_by(
                patient_id=patient.id,
                alert_type='Missing Data',
                status='ACTIVE'
            ).first()
            if not existing_gap_alert:
                db.session.add(Alert(
                    patient_id=patient.id,
                    alert_type='Missing Data',
                    severity='MEDIUM',
                    message=f"Patient hasn't checked in for {days_since_last_log} days."
                ))

    # 5. Wearable Sync Gaps (Missing wearable data detection)
    device = WearableDevice.query.filter_by(patient_id=patient.id, connection_status='CONNECTED').first()
    if device:
        if device.last_synced_at:
            # last_synced_at is datetime, today is date. Convert both.
            days_since_sync = (datetime.utcnow() - device.last_synced_at).days
            if days_since_sync >= 2:
                db.session.add(ClinicalInsight(
                    patient_id=patient.id,
                    insight_type='MissingWearableData',
                    insight_text=f"No wearable data received for {days_since_sync} days."
                ))
                
                # Trigger active alert
                existing_alert = Alert.query.filter_by(
                    patient_id=patient.id,
                    alert_type='Missing Data',
                    message=f"No wearable data received for {days_since_sync} days.",
                    status='ACTIVE'
                ).first()
                if not existing_alert:
                    db.session.add(Alert(
                        patient_id=patient.id,
                        alert_type='Missing Data',
                        severity='MEDIUM',
                        message=f"No wearable data received for {days_since_sync} days."
                    ))
        else:
            db.session.add(ClinicalInsight(
                patient_id=patient.id,
                insight_type='MissingWearableData',
                insight_text="Wearable device connected but has never been synced."
            ))
            
        # 6. Missing Specific Wearable Metrics (e.g. sleep data missing for 3 days)
        recent_summaries = [s for s in summaries if s.date >= (today - timedelta(days=3))]
        if recent_summaries and len(recent_summaries) >= 3 and all(s.sleep_hours is None for s in recent_summaries):
            db.session.add(ClinicalInsight(
                patient_id=patient.id,
                insight_type='MissingWearableMetric',
                insight_text="Sleep data unavailable for the last 3 days."
            ))

    # 7. Wearable steps trend (average daily steps change)
    first_steps = [s.total_steps for s in first_half_sums if s.total_steps is not None]
    second_steps = [s.total_steps for s in second_half_sums if s.total_steps is not None]
    if first_steps and second_steps:
        avg_s1 = sum(first_steps) / len(first_steps)
        avg_s2 = sum(second_steps) / len(second_steps)
        if avg_s1 > 0:
            pct_change = ((avg_s2 - avg_s1) / avg_s1) * 100
            if abs(pct_change) >= 15:
                direction = "increased" if pct_change > 0 else "decreased"
                db.session.add(ClinicalInsight(
                    patient_id=patient.id,
                    insight_type='StepsTrend',
                    insight_text=f"Patient's average daily steps {direction} by {abs(round(pct_change))}% over the last 30 days."
                ))

    # 8. Wearable sleep trend
    first_sleep = [s.sleep_hours for s in first_half_sums if s.sleep_hours is not None]
    second_sleep = [s.sleep_hours for s in second_half_sums if s.sleep_hours is not None]
    if first_sleep and second_sleep:
        avg_sl1 = sum(first_sleep) / len(first_sleep)
        avg_sl2 = sum(second_sleep) / len(second_sleep)
        diff_sleep = avg_sl2 - avg_sl1
        if abs(diff_sleep) >= 0.5:
            direction = "increased" if diff_sleep > 0 else "decreased"
            db.session.add(ClinicalInsight(
                patient_id=patient.id,
                insight_type='SleepTrend',
                insight_text=f"Average sleep duration {direction} from {round(avg_sl1, 1)} hours to {round(avg_sl2, 1)} hours."
            ))

    # 9. Wearable Blood Pressure drift
    first_bps = [s.systolic_bp for s in first_half_sums if s.systolic_bp is not None]
    second_bps = [s.systolic_bp for s in second_half_sums if s.systolic_bp is not None]
    if first_bps and second_bps:
        avg_bp1 = sum(first_bps) / len(first_bps)
        avg_bp2 = sum(second_bps) / len(second_bps)
        if abs(avg_bp2 - avg_bp1) >= 8:
            db.session.add(ClinicalInsight(
                patient_id=patient.id,
                insight_type='BPTrend',
                insight_text="Recorded blood pressure values changed during the monitoring period. Review alongside medication adherence and other clinical information."
            ))

    # 10. Adherence Rate drop check
    score = calculate_adherence_score(patient)['total']
    if score < 50:
        db.session.add(ClinicalInsight(
            patient_id=patient.id,
            insight_type='LowAdherence',
            insight_text=f"Care Adherence Score has dropped to a low index of {score}%."
        ))
        # Trigger alert
        existing_adh_alert = Alert.query.filter_by(
            patient_id=patient.id,
            alert_type='Compliance',
            status='ACTIVE'
        ).first()
        if not existing_adh_alert:
            db.session.add(Alert(
                patient_id=patient.id,
                alert_type='Compliance',
                severity='MEDIUM',
                message=f"Low patient care adherence score flagged: {score}%"
            ))

    db.session.commit()
