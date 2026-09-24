from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from datetime import datetime, date, timedelta
from app.extensions import db
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.medication import Medication
from app.models.daily_log import DailyHealthLog
from app.models.recommendation import Alert, DoctorNote, AISummary, ClinicalInsight, AuditLog
from app.models.medical_report import MedicalReport
from app.services.compliance_engine import calculate_adherence_score
from app.services.bmi_service import get_bmi_category

doctor_bp = Blueprint('doctor', __name__)

class DoctorProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    specialization = StringField('Medical Specialization', validators=[DataRequired(), Length(max=100)])
    clinic_name = StringField('Hospital / Clinic Affiliation', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Contact Phone Number', validators=[Optional(), Length(max=20)])
    submit = SubmitField('Save Profile')

@doctor_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'DOCTOR':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    doctor = current_user.doctor_profile
    if not doctor:
        flash('Please complete your profile to access the panel.', 'warning')
        return redirect(url_for('doctor.create_profile'))
        
    # Get filters from query parameters
    filter_condition = request.args.get('condition', '')
    filter_adherence = request.args.get('adherence', '')
    filter_search = request.args.get('search', '').lower()
    
    patients = doctor.patients
    
    # Calculate stats
    total_patients = len(patients)
    active_count = 0
    attention_count = 0
    missing_logs_count = 0
    total_adherence_sum = 0
    
    seven_days_ago = datetime.utcnow().date() - timedelta(days=7)
    
    patient_list_data = []
    for p in patients:
        # Calculate adherence score
        score_data = calculate_adherence_score(p)
        score = score_data['total']
        total_adherence_sum += score
        
        # Last check-in
        last_log = DailyHealthLog.query.filter_by(patient_id=p.id).order_by(DailyHealthLog.log_date.desc()).first()
        last_checkin_date = last_log.log_date if last_log else None
        
        # Active check
        is_active = False
        if last_checkin_date and last_checkin_date >= seven_days_ago:
            is_active = True
            active_count += 1
        elif last_checkin_date:
            missing_logs_count += 1
            
        # Alerts check
        active_alerts = Alert.query.filter_by(patient_id=p.id, status='ACTIVE').all()
        if active_alerts:
            attention_count += 1
            
        latest_report = p.medical_reports[-1].uploaded_at if p.medical_reports else None
        
        patient_data = {
            'patient': p,
            'adherence': score,
            'last_checkin': last_checkin_date,
            'latest_report': latest_report,
            'has_active_alerts': len(active_alerts) > 0,
            'alerts_count': len(active_alerts),
            'is_active': is_active
        }
        
        # Apply filters in memory
        if filter_condition and p.primary_condition != filter_condition:
            continue
        if filter_adherence:
            if filter_adherence == 'high' and score < 80:
                continue
            elif filter_adherence == 'medium' and (score < 50 or score >= 80):
                continue
            elif filter_adherence == 'low' and score >= 50:
                continue
        if filter_search and (filter_search not in p.name.lower() and filter_search not in p.user.email.lower()):
            continue
            
        patient_list_data.append(patient_data)
        
    avg_adherence = round(total_adherence_sum / total_patients) if total_patients > 0 else 0
    
    # Fetch all active alerts for this doctor's patients
    patient_ids = [p.id for p in doctor.patients]
    recent_alerts = Alert.query.filter(
        Alert.patient_id.in_(patient_ids) if patient_ids else False,
        Alert.status == 'ACTIVE'
    ).order_by(Alert.created_at.desc()).all()
    
    return render_template(
        'doctor/dashboard.html',
        doctor=doctor,
        patients=patient_list_data,
        total_patients=total_patients,
        active_patients=active_count,
        attention_patients=attention_count,
        missing_logs=missing_logs_count,
        avg_adherence=avg_adherence,
        recent_alerts=recent_alerts,
        filter_condition=filter_condition,
        filter_adherence=filter_adherence,
        filter_search=request.args.get('search', '')
    )

@doctor_bp.route('/profile/create', methods=['GET', 'POST'])
@login_required
def create_profile():
    if current_user.role != 'DOCTOR':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    doctor = current_user.doctor_profile
    form = DoctorProfileForm(obj=doctor)
    
    if form.validate_on_submit():
        if not doctor:
            doctor = Doctor(
                user_id=current_user.id,
                name=form.name.data,
                specialization=form.specialization.data,
                phone=form.phone.data,
                clinic_name=form.clinic_name.data
            )
            db.session.add(doctor)
            flash('Profile completed successfully!', 'success')
        else:
            doctor.name = form.name.data
            doctor.specialization = form.specialization.data
            doctor.phone = form.phone.data
            doctor.clinic_name = form.clinic_name.data
            flash('Profile updated successfully!', 'success')
            
        db.session.commit()
        return redirect(url_for('doctor.dashboard'))
        
    return render_template('doctor/profile_form.html', form=form, doctor=doctor, action="create" if not doctor else "edit")

@doctor_bp.route('/patient/<patient_id>')
@login_required
def patient_detail(patient_id):
    if current_user.role != 'DOCTOR':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    
    if not patient or patient not in doctor.patients:
        flash('Patient record not found.', 'danger')
        return redirect(url_for('doctor.dashboard'))
        
    # Log access
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=patient.id,
        action="VIEW_PATIENT_DETAIL",
        ip_address=request.remote_addr
    ))
    db.session.commit()
        
    # Trigger real-time trend insights and AI progress summaries
    from app.services.insight_engine import run_insight_engine
    from app.services.ai_service import generate_patient_summary
    from flask import current_app
    try:
        run_insight_engine(patient)
        generate_patient_summary(patient)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error running real-time insights/AI summaries: {str(e)}")
        
    today = datetime.utcnow().date()
    
    # Compliance Metrics
    adherence = calculate_adherence_score(patient)
    
    # Prescriptions (Active & Historical)
    prescriptions = Medication.query.filter_by(patient_id=patient.id).order_by(Medication.is_active.desc(), Medication.created_at.desc()).all()
    
    # Active alerts
    alerts = Alert.query.filter_by(patient_id=patient.id, status='ACTIVE').order_by(Alert.created_at.desc()).all()
    
    # Clinician notes
    notes = DoctorNote.query.filter_by(patient_id=patient.id, doctor_id=doctor.id).order_by(DoctorNote.created_at.desc()).all()
    
    # AI summary
    latest_summary = AISummary.query.filter_by(patient_id=patient.id).order_by(AISummary.created_at.desc()).first()
    
    # Insights
    insights = ClinicalInsight.query.filter_by(patient_id=patient.id).order_by(ClinicalInsight.created_at.desc()).all()
    
    # Fetch last 30 logs for trends
    start_date = today - timedelta(days=30)
    logs = DailyHealthLog.query.filter(
        DailyHealthLog.patient_id == patient.id,
        DailyHealthLog.log_date >= start_date
    ).order_by(DailyHealthLog.log_date.asc()).all()
    
    dates = [l.log_date.strftime('%b %d') for l in logs]
    glucose = [l.blood_glucose for l in logs if l.blood_glucose is not None]
    glucose_dates = [l.log_date.strftime('%b %d') for l in logs if l.blood_glucose is not None]
    bp_sys = [l.systolic_bp for l in logs if l.systolic_bp is not None]
    bp_dia = [l.diastolic_bp for l in logs if l.diastolic_bp is not None]
    bp_dates = [l.log_date.strftime('%b %d') for l in logs if l.systolic_bp is not None]
    weights = [l.weight for l in logs if l.weight is not None]
    weight_dates = [l.log_date.strftime('%b %d') for l in logs if l.weight is not None]
    
    # Wearable & Continuous Monitoring Calculations
    from app.models.wearable import WearableDevice, DailyHealthSummary
    device = WearableDevice.query.filter_by(patient_id=patient.id, connection_status='CONNECTED').first()
    
    avg_steps = 0
    steps_pct_change = 0
    avg_sleep = 0.0
    sleep_pct_change = 0
    weight_change = 0.0
    start_weight = patient.weight
    current_weight = patient.weight
    avg_resting_hr = 0
    avg_bp_systolic = 0
    avg_bp_diastolic = 0
    
    summaries = DailyHealthSummary.query.filter(
        DailyHealthSummary.patient_id == patient.id,
        DailyHealthSummary.date >= start_date
    ).order_by(DailyHealthSummary.date.asc()).all()
    
    mid_point = start_date + timedelta(days=15)
    first_half_sums = [s for s in summaries if s.date < mid_point]
    second_half_sums = [s for s in summaries if s.date >= mid_point]
    
    if summaries:
        steps_vals = [s.total_steps for s in summaries if s.total_steps is not None]
        if steps_vals:
            avg_steps = int(sum(steps_vals) / len(steps_vals))
            first_half_steps = [s.total_steps for s in first_half_sums if s.total_steps is not None]
            second_half_steps = [s.total_steps for s in second_half_sums if s.total_steps is not None]
            if first_half_steps and second_half_steps:
                avg_s1 = sum(first_half_steps) / len(first_half_steps)
                avg_s2 = sum(second_half_steps) / len(second_half_steps)
                if avg_s1 > 0:
                    steps_pct_change = int(((avg_s2 - avg_s1) / avg_s1) * 100)
                    
        sleep_vals = [s.sleep_hours for s in summaries if s.sleep_hours is not None]
        if sleep_vals:
            avg_sleep = round(sum(sleep_vals) / len(sleep_vals), 1)
            first_half_sleep = [s.sleep_hours for s in first_half_sums if s.sleep_hours is not None]
            second_half_sleep = [s.sleep_hours for s in second_half_sums if s.sleep_hours is not None]
            if first_half_sleep and second_half_sleep:
                avg_sl1 = sum(first_half_sleep) / len(first_half_sleep)
                avg_sl2 = sum(second_half_sleep) / len(second_half_sleep)
                if avg_sl1 > 0:
                    sleep_pct_change = int(((avg_sl2 - avg_sl1) / avg_sl1) * 100)
                    
        weight_vals = [s.weight for s in summaries if s.weight is not None]
        if weight_vals:
            start_weight = weight_vals[0]
            current_weight = weight_vals[-1]
            weight_change = round(current_weight - start_weight, 1)
            
        rhr_vals = [s.resting_heart_rate for s in summaries if s.resting_heart_rate is not None]
        if rhr_vals:
            avg_resting_hr = int(sum(rhr_vals) / len(rhr_vals))
            
        sys_bp_vals = [s.systolic_bp for s in summaries if s.systolic_bp is not None]
        dia_bp_vals = [s.diastolic_bp for s in summaries if s.diastolic_bp is not None]
        if sys_bp_vals and dia_bp_vals:
            avg_bp_systolic = int(sum(sys_bp_vals) / len(sys_bp_vals))
            avg_bp_diastolic = int(sum(dia_bp_vals) / len(dia_bp_vals))
            
    # Journal Entries (Last 5)
    from app.models.journal import JournalEntry
    journals = JournalEntry.query.filter_by(patient_id=patient.id).order_by(JournalEntry.entry_date.desc()).limit(5).all()
    
    # 1. Historical laboratory reports comparison
    reports = MedicalReport.query.filter_by(patient_id=patient.id, is_processed=True).order_by(MedicalReport.uploaded_at.desc()).all()
    report_comparison = {}
    if len(reports) >= 1:
        latest_report = reports[0]
        # Get lab results of latest report
        latest_results = {r.parameter_name: r for r in latest_report.lab_results}
        
        # Get lab results of previous report if exists
        prev_results = {}
        if len(reports) >= 2:
            prev_report = reports[1]
            prev_results = {r.parameter_name: r for r in prev_report.lab_results}
            
        for param_name, res in latest_results.items():
            latest_val = res.parameter_value
            prev_res = prev_results.get(param_name)
            prev_val = prev_res.parameter_value if prev_res else None
            
            diff = round(latest_val - prev_val, 2) if prev_val is not None else None
            pct_change = round((diff / prev_val) * 100, 1) if (diff is not None and prev_val) else None
            
            # Clinical safety direction check: neutral trend descriptors
            if prev_val is None:
                trend = 'Baseline'
            elif abs(latest_val - prev_val) < 0.01:
                trend = 'No significant recorded change'
            elif latest_val > prev_val:
                trend = 'Increased'
            else:
                trend = 'Decreased'
                
            report_comparison[param_name] = {
                'latest_value': latest_val,
                'prev_value': prev_val,
                'diff': diff,
                'pct_change': pct_change,
                'unit': res.unit,
                'normal_range': res.normal_range,
                'trend': trend,
                'confidence': res.confidence
            }
            
    # 2. Fetch all AI summaries chronologically for dropdown
    historical_summaries = AISummary.query.filter_by(patient_id=patient.id).order_by(AISummary.created_at.desc()).all()

    # 3. Compile patient timeline events chronologically
    timeline_events = []
    
    # Registration event
    timeline_events.append({
        'date': patient.created_at or datetime.utcnow(),
        'type': 'profile',
        'title': 'Patient Profile Created',
        'badge_color': 'teal',
        'icon': 'bi-person-plus',
        'description': f"Baseline profile registered with condition: {patient.primary_condition}."
    })
    
    # Lab report events
    patient_reports = MedicalReport.query.filter_by(patient_id=patient.id, is_processed=True).all()
    for rep in patient_reports:
        results_str = ", ".join([f"{r.parameter_name} ({r.parameter_value} {r.unit})" for r in rep.lab_results])
        timeline_events.append({
            'date': rep.uploaded_at,
            'type': 'report',
            'title': 'Medical Laboratory Report Processed',
            'badge_color': 'danger',
            'icon': 'bi-file-earmark-medical',
            'description': f"File '{rep.file_name}' uploaded. Extracted parameters: {results_str or 'None'}."
        })
        
    # Doctor note events
    patient_notes = DoctorNote.query.filter_by(patient_id=patient.id).all()
    for note in patient_notes:
        timeline_events.append({
            'date': note.created_at,
            'type': 'note',
            'title': 'Clinician Consult Note Added',
            'badge_color': 'primary',
            'icon': 'bi-chat-left-text',
            'description': f"Note by {note.doctor.name if note.doctor else 'Clinician'}: \"{note.note_text}\""
        })
        
    # AI progress summary events
    for summary in historical_summaries:
        timeline_events.append({
            'date': summary.created_at,
            'type': 'ai_summary',
            'title': 'AI Progress Summary Generated',
            'badge_color': 'warning',
            'icon': 'bi-magic',
            'description': f"Analyzed weekly metrics from {summary.start_date.strftime('%b %d')} to {summary.end_date.strftime('%b %d, %Y')}."
        })
        
    # Medication prescribed events
    medications = Medication.query.filter_by(patient_id=patient.id).all()
    for med in medications:
        status_text = "active" if med.is_active else "inactive/completed"
        timeline_events.append({
            'date': datetime.combine(med.start_date, datetime.min.time()),
            'type': 'medication',
            'title': 'Medication Prescribed',
            'badge_color': 'success',
            'icon': 'bi-capsule',
            'description': f"Prescribed {med.name} ({med.dosage}, {med.frequency}) starting {med.start_date.strftime('%b %d, %Y')}. Status: {status_text}."
        })
        
    # Daily logs / Symptoms
    daily_logs = DailyHealthLog.query.filter_by(patient_id=patient.id).all()
    for log in daily_logs:
        log_desc = f"Logged daily metrics. Mood: {log.mood or 'N/A'}, Energy: {log.energy or 'N/A'}."
        if log.symptoms:
            log_desc += f" Reported symptoms: {log.symptoms}."
        timeline_events.append({
            'date': datetime.combine(log.log_date, datetime.min.time()),
            'type': 'daily_log',
            'title': 'Daily Health Log Submitted',
            'badge_color': 'info',
            'icon': 'bi-journal-check',
            'description': log_desc
        })
        
    # Wearable connection changes
    wearable_audits = AuditLog.query.filter_by(patient_id=patient.id).filter(AuditLog.action.like('%WEARABLE%')).all()
    for audit in wearable_audits:
        timeline_events.append({
            'date': audit.timestamp,
            'type': 'wearable',
            'title': 'Wearable Connection Event',
            'badge_color': 'dark',
            'icon': 'bi-smartwatch',
            'description': f"Action details: {audit.action}."
        })
        
    # Clinical insights
    clinical_insights = ClinicalInsight.query.filter_by(patient_id=patient.id).all()
    for insight in clinical_insights:
        timeline_events.append({
            'date': insight.created_at,
            'type': 'insight',
            'title': f"Clinical Insight: {insight.insight_type}",
            'badge_color': 'secondary',
            'icon': 'bi-lightbulb',
            'description': insight.insight_text
        })
        
    # Sort events chronologically descending
    timeline_events.sort(key=lambda x: x['date'], reverse=True)

    # Machine Learning Inference (Random Forest + K-Means)
    from app.ml.inference import predict_patient_progress, get_compliance_archetype
    ml_result = predict_patient_progress(patient)
    ml_archetype = get_compliance_archetype(patient)
    
    return render_template(
        'doctor/patient_detail.html',
        patient=patient,
        bmi_category=get_bmi_category(patient.bmi) if patient.bmi else 'N/A',
        adherence=adherence,
        prescriptions=prescriptions,
        alerts=alerts,
        notes=notes,
        latest_summary=latest_summary,
        historical_summaries=historical_summaries,
        report_comparison=report_comparison,
        insights=insights,
        journals=journals,
        dates=dates,
        glucose=glucose,
        glucose_dates=glucose_dates,
        bp_sys=bp_sys,
        bp_dia=bp_dia,
        bp_dates=bp_dates,
        weights=weights,
        weight_dates=weight_dates,
        ml_prediction=ml_result['prediction'],
        ml_confidence=round(ml_result['confidence'] * 100),
        ml_archetype=ml_archetype,
        device=device,
        avg_steps=avg_steps,
        steps_pct_change=steps_pct_change,
        avg_sleep=avg_sleep,
        sleep_pct_change=sleep_pct_change,
        weight_change=weight_change,
        start_weight=start_weight,
        current_weight=current_weight,
        avg_resting_hr=avg_resting_hr,
        avg_bp_systolic=avg_bp_systolic,
        avg_bp_diastolic=avg_bp_diastolic,
        timeline_events=timeline_events
    )

@doctor_bp.route('/patient/<patient_id>/prescribe', methods=['POST'])
@login_required
def prescribe(patient_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    
    if not patient or patient not in doctor.patients:
        return jsonify({'error': 'Patient not found'}), 404
        
    name = request.form.get('name')
    dosage = request.form.get('dosage')
    frequency = request.form.get('frequency')
    timing = request.form.get('timing')
    instructions = request.form.get('instructions')
    start_date_str = request.form.get('start_date', datetime.utcnow().strftime('%Y-%m-%d'))
    
    if not name or not dosage or not frequency:
        flash('Medication Name, Dosage, and Frequency are required.', 'danger')
        return redirect(url_for('doctor.patient_detail', patient_id=patient.id))
        
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    med = Medication(
        patient_id=patient.id,
        prescribed_by_id=doctor.id,
        name=name,
        dosage=dosage,
        frequency=frequency,
        timing=timing,
        instructions=instructions,
        start_date=start_date,
        is_active=True
    )
    
    db.session.add(med)
    
    # Audit log
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"PRESCRIBE med={name} patient_id={patient.id}",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    
    flash(f"Prescription for {name} added successfully.", 'success')
    return redirect(url_for('doctor.patient_detail', patient_id=patient.id))

@doctor_bp.route('/patient/<patient_id>/prescribe/stop/<medication_id>', methods=['POST'])
@login_required
def stop_prescription(patient_id, medication_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    med = db.session.get(Medication, medication_id)
    
    if not patient or patient not in doctor.patients or not med or med.patient_id != patient.id:
        flash('Invalid medication or patient relationship.', 'danger')
        return redirect(url_for('doctor.dashboard'))
        
    med.is_active = False
    med.end_date = datetime.utcnow().date()
    
    # Audit log
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"STOP_PRESCRIBE med_id={med.id} patient_id={patient.id}",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    
    flash(f"Prescription for {med.name} deactivated.", 'success')
    return redirect(url_for('doctor.patient_detail', patient_id=patient.id))

@doctor_bp.route('/patient/<patient_id>/note', methods=['POST'])
@login_required
def add_note(patient_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    
    if not patient or patient not in doctor.patients:
        flash('Patient not found.', 'danger')
        return redirect(url_for('doctor.dashboard'))
        
    note_text = request.form.get('note_text')
    if not note_text:
        flash('Note content cannot be empty.', 'danger')
        return redirect(url_for('doctor.patient_detail', patient_id=patient.id))
        
    note = DoctorNote(
        patient_id=patient.id,
        doctor_id=doctor.id,
        note_text=note_text
    )
    db.session.add(note)
    db.session.commit()
    
    flash('Clinician note added.', 'success')
    return redirect(url_for('doctor.patient_detail', patient_id=patient.id))

@doctor_bp.route('/alert/resolve/<alert_id>', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    alert = db.session.get(Alert, alert_id)
    
    if not alert or alert.patient not in doctor.patients:
        return jsonify({'error': 'Alert not found'}), 404
        
    alert.status = 'RESOLVED'
    alert.resolved_by_id = doctor.id
    alert.resolved_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True})

@doctor_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'ADMIN':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    from app.models.user import User
    from app.models.doctor import Doctor
    from app.models.patient import Patient
    
    # Query system stats
    total_users = User.query.count()
    total_doctors = Doctor.query.count()
    total_patients = Patient.query.count()
    
    # List of all users for activation/deactivation
    users_list = User.query.order_by(User.created_at.desc()).all()
    
    # Query recent security audit logs
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(50).all()
    
    return render_template(
        'doctor/admin.html',
        total_users=total_users,
        total_doctors=total_doctors,
        total_patients=total_patients,
        users=users_list,
        audit_logs=logs
    )

@doctor_bp.route('/admin/user/toggle/<user_id>', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    if current_user.role != 'ADMIN':
        return jsonify({'error': 'Unauthorized'}), 403
        
    from app.models.user import User
    # Using Session.get() as recommended in SQLAlchemy 2.0+
    user = db.session.get(User, user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot self-deactivate administrator account.'}), 400
        
    user.is_active_user = not user.is_active_user
    
    # Write audit log
    action = "ACTIVATE_USER" if user.is_active_user else "DEACTIVATE_USER"
    audit = AuditLog(
        user_id=current_user.id,
        action=f"{action} target_user={user.email}",
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_status': user.is_active_user,
        'msg': f"User account {'activated' if user.is_active_user else 'deactivated'} successfully."
    })

@doctor_bp.route('/ai-summary/acknowledge/<summary_id>', methods=['POST'])
@login_required
def acknowledge_ai_summary(summary_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    summary = db.session.get(AISummary, summary_id)
    
    if not summary or summary.patient not in doctor.patients:
        return jsonify({'error': 'AI Summary not found'}), 404
        
    summary.is_acknowledged = True
    
    # Audit log
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=summary.patient_id,
        action=f"ACKNOWLEDGE_AI_SUMMARY summary_id={summary_id}",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    return jsonify({'success': True})

@doctor_bp.route('/patient/<patient_id>/ml/acknowledge', methods=['POST'])
@login_required
def acknowledge_ml_prediction(patient_id):
    if current_user.role != 'DOCTOR':
        return jsonify({'error': 'Unauthorized'}), 403
        
    doctor = current_user.doctor_profile
    patient = db.session.get(Patient, patient_id)
    
    if not patient or patient not in doctor.patients:
        return jsonify({'error': 'Patient not found'}), 404
        
    patient.ml_acknowledged = True
    
    # Audit log
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=patient.id,
        action="ACKNOWLEDGE_ML_PREDICTION",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    return jsonify({'success': True})

