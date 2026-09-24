import json
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.patient import Patient
from app.models.wearable import WearableDevice, HealthMetric, DailyHealthSummary
from app.models.recommendation import ClinicalInsight, AuditLog
from app.services.health_sync_service import connect_wearable_provider, disconnect_wearable_provider, sync_patient_health_data
from app.services.health_summary_service import aggregate_daily_health_summary
from app.services.bmi_service import get_bmi_category

wearables_bp = Blueprint('wearables', __name__)

@wearables_bp.route('/patient/wearables')
@login_required
def manage_wearables():
    if current_user.role != 'PATIENT':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    patient = current_user.patient_profile
    if not patient:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('patient.create_profile'))
        
    # Get active/connected device details
    device = WearableDevice.query.filter_by(patient_id=patient.id, connection_status='CONNECTED').first()
    
    # Query today's summary
    today = date.today()
    summary = DailyHealthSummary.query.filter_by(patient_id=patient.id, date=today).first()
    
    # Extract sources dictionary
    sources = {}
    if summary and summary.data_sources:
        try:
            sources = json.loads(summary.data_sources)
        except Exception:
            pass
            
    return render_template(
        'patient/wearables.html',
        patient=patient,
        device=device,
        summary=summary,
        sources=sources
    )


@wearables_bp.route('/api/patient/wearables/connect', methods=['POST'])
@login_required
def api_connect_wearable():
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    data = request.get_json() or {}
    
    provider = data.get('provider', 'Demo Wearable')
    device_name = data.get('device_name', 'Smart Health Device')
    device_type = data.get('device_type', 'Smartwatch')
    consent = data.get('health_data_consent', False)
    
    if not consent:
        return jsonify({'error': 'Consent is required to synchronize health data.'}), 400
        
    try:
        # 1. Update patient consent status
        patient.health_data_consent = True
        db.session.commit()
        
        # 2. Connect device
        device = connect_wearable_provider(patient.id, provider, device_name, device_type)
        
        # 3. Perform initial 7-day synchronization in real-time
        sync_patient_health_data(patient.id, days=7)
        
        return jsonify({
            'success': True,
            'message': f"Device '{device_name}' connected successfully! 7 days of historical logs synced.",
            'device_id': device.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@wearables_bp.route('/api/patient/wearables/disconnect', methods=['POST'])
@login_required
def api_disconnect_wearable():
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    data = request.get_json() or {}
    provider = data.get('provider', 'Demo Wearable')
    
    try:
        # Revoke consent
        patient.health_data_consent = False
        db.session.commit()
        
        # Disconnect wearable
        success = disconnect_wearable_provider(patient.id, provider)
        if success:
            return jsonify({'success': True, 'message': 'Wearable device disconnected and data sharing consent revoked.'})
        return jsonify({'error': 'No connected device found to disconnect.'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@wearables_bp.route('/api/patient/wearables/sync', methods=['POST'])
@login_required
def api_sync_wearable():
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    if not patient.health_data_consent:
        return jsonify({'error': 'Cannot sync: data sharing consent is revoked.'}), 400
        
    data = request.get_json() or {}
    days = int(data.get('days', 7))
    
    # Constrain days to avoid timeout
    if days not in [7, 30, 90]:
        days = 7
        
    result = sync_patient_health_data(patient.id, days=days)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@wearables_bp.route('/api/patient/health-metrics', methods=['GET'])
@login_required
def api_get_health_metrics():
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    metric_type = request.args.get('metric_type')
    days = int(request.args.get('days', 7))
    
    start_date = date.today() - timedelta(days=days)
    
    query = HealthMetric.query.filter(
        HealthMetric.patient_id == patient.id,
        HealthMetric.timestamp >= datetime.combine(start_date, datetime.min.time())
    )
    if metric_type:
        query = query.filter_by(metric_type=metric_type)
        
    metrics = query.order_by(HealthMetric.timestamp.asc()).all()
    
    return jsonify([{
        'id': m.id,
        'metric_type': m.metric_type,
        'value': m.value,
        'unit': m.unit,
        'timestamp': m.timestamp.isoformat(),
        'source': m.source,
        'confidence': m.confidence
    } for m in metrics])


@wearables_bp.route('/api/patient/health-metrics/daily', methods=['GET'])
@login_required
def api_get_daily_summaries():
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    days = int(request.args.get('days', 7))
    
    start_date = date.today() - timedelta(days=days - 1)
    
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient.id,
        DailyHealthSummary.date >= start_date
    ).order_by(DailyHealthSummary.date.asc()).all()
    
    return jsonify([{
        'date': s.date.strftime('%Y-%m-%d'),
        'total_steps': s.total_steps,
        'calories_burned': s.calories_burned,
        'active_minutes': s.active_minutes,
        'average_heart_rate': s.average_heart_rate,
        'resting_heart_rate': s.resting_heart_rate,
        'sleep_hours': s.sleep_hours,
        'weight': s.weight,
        'systolic_bp': s.systolic_bp,
        'diastolic_bp': s.diastolic_bp,
        'blood_glucose': s.blood_glucose,
        'spo2': s.spo2,
        'sources': json.loads(s.data_sources) if s.data_sources else {}
    } for s in summaries])


@wearables_bp.route('/api/patient/health-metrics/trends', methods=['GET'])
@login_required
def api_get_trends_data():
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    days = int(request.args.get('days', 7))
    
    start_date = date.today() - timedelta(days=days - 1)
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient.id,
        DailyHealthSummary.date >= start_date
    ).order_by(DailyHealthSummary.date.asc()).all()
    
    return jsonify({
        'dates': [s.date.strftime('%b %d') for s in summaries],
        'steps': [s.total_steps for s in summaries],
        'weight': [s.weight for s in summaries],
        'sleep': [s.sleep_hours for s in summaries],
        'heart_rate': [s.average_heart_rate for s in summaries],
        'resting_hr': [s.resting_heart_rate for s in summaries],
        'bp_sys': [s.systolic_bp for s in summaries],
        'bp_dia': [s.diastolic_bp for s in summaries],
        'glucose': [s.blood_glucose for s in summaries],
        'spo2': [s.spo2 for s in summaries],
        'active_minutes': [s.active_minutes for s in summaries]
    })


@wearables_bp.route('/api/doctor/patients/<patient_id>/health-summary', methods=['GET'])
@login_required
def api_doctor_patient_health_summary(patient_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    if not patient or patient not in doctor.patients:
        return jsonify({'error': 'Patient not found or unauthorized.'}), 404
        
    # Log access
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=patient.id,
        action="VIEW_HEALTH_SUMMARY",
        ip_address=request.remote_addr
    ))
    db.session.commit()
        
    days = int(request.args.get('days', 7))
    start_date = date.today() - timedelta(days=days - 1)
    
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient_id,
        DailyHealthSummary.date >= start_date
    ).order_by(DailyHealthSummary.date.desc()).all()
    
    return jsonify([{
        'date': s.date.strftime('%Y-%m-%d'),
        'total_steps': s.total_steps,
        'calories_burned': s.calories_burned,
        'active_minutes': s.active_minutes,
        'average_heart_rate': s.average_heart_rate,
        'resting_heart_rate': s.resting_heart_rate,
        'sleep_hours': s.sleep_hours,
        'weight': s.weight,
        'systolic_bp': s.systolic_bp,
        'diastolic_bp': s.diastolic_bp,
        'blood_glucose': s.blood_glucose,
        'spo2': s.spo2
    } for s in summaries])


@wearables_bp.route('/api/doctor/patients/<patient_id>/health-trends', methods=['GET'])
@login_required
def api_doctor_patient_health_trends(patient_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    if not patient or patient not in doctor.patients:
        return jsonify({'error': 'Patient not found or unauthorized.'}), 404
        
    # Log access
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=patient.id,
        action="VIEW_HEALTH_TRENDS",
        ip_address=request.remote_addr
    ))
    db.session.commit()
        
    days = int(request.args.get('days', 7))
    start_date = date.today() - timedelta(days=days - 1)
    
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient_id,
        DailyHealthSummary.date >= start_date
    ).order_by(DailyHealthSummary.date.asc()).all()
    
    return jsonify({
        'dates': [s.date.strftime('%b %d') for s in summaries],
        'steps': [s.total_steps for s in summaries],
        'weight': [s.weight for s in summaries],
        'sleep': [s.sleep_hours for s in summaries],
        'heart_rate': [s.average_heart_rate for s in summaries],
        'resting_hr': [s.resting_heart_rate for s in summaries],
        'bp_sys': [s.systolic_bp for s in summaries],
        'bp_dia': [s.diastolic_bp for s in summaries],
        'glucose': [s.blood_glucose for s in summaries],
        'spo2': [s.spo2 for s in summaries],
        'active_minutes': [s.active_minutes for s in summaries]
    })


@wearables_bp.route('/api/doctor/patients/<patient_id>/clinical-insights', methods=['GET'])
@login_required
def api_doctor_patient_clinical_insights(patient_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    if not patient or patient not in doctor.patients:
        return jsonify({'error': 'Patient not found or unauthorized.'}), 404
        
    # Log access
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=patient.id,
        action="VIEW_CLINICAL_INSIGHTS",
        ip_address=request.remote_addr
    ))
    db.session.commit()
        
    insights = ClinicalInsight.query.filter_by(patient_id=patient_id).order_by(ClinicalInsight.created_at.desc()).all()
    
    return jsonify([{
        'id': i.id,
        'insight_type': i.insight_type,
        'insight_text': i.insight_text,
        'created_at': i.created_at.isoformat()
    } for i in insights])
