from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app.extensions import db
from app.models.medication import Medication, MedicationLog

medication_bp = Blueprint('medication', __name__)

@medication_bp.route('/history')
@login_required
def history():
    if current_user.role != 'PATIENT':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    patient = current_user.patient_profile
    if not patient:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('patient.create_profile'))
        
    # Get active medications
    medications = Medication.query.filter_by(patient_id=patient.id, is_active=True).all()
    
    today = datetime.utcnow().date()
    start_grid_date = today - timedelta(days=6)  # Last 7 days grid
    
    # Pre-build date list for headers
    date_grid = [start_grid_date + timedelta(days=i) for i in range(7)]
    
    meds_data = []
    for med in medications:
        # Calculate Adherence Percentage
        total_days = (today - med.start_date).days + 1
        if med.end_date and med.end_date < today:
            total_days = (med.end_date - med.start_date).days + 1
        total_days = max(1, total_days)  # Avoid division by zero
        
        taken_count = MedicationLog.query.filter_by(
            medication_id=med.id, 
            status='TAKEN'
        ).count()
        
        adherence_rate = round((taken_count / total_days) * 100) if total_days > 0 else 0
        
        # Get logs for the grid range
        grid_logs = {}
        for d in date_grid:
            log_item = MedicationLog.query.filter_by(
                medication_id=med.id, 
                log_date=d
            ).first()
            grid_logs[d] = log_item.status if log_item else None
            
        meds_data.append({
            'medication': med,
            'adherence': adherence_rate,
            'grid_logs': grid_logs
        })
        
    return render_template(
        'patient/medication.html', 
        meds_data=meds_data, 
        date_grid=date_grid,
        today=today
    )

@medication_bp.route('/log/<medication_id>', methods=['POST'])
@login_required
def log_adherence(medication_id):
    if current_user.role != 'PATIENT':
        return jsonify({'error': 'Unauthorized'}), 403
        
    patient = current_user.patient_profile
    med = Medication.query.get_or_404(medication_id)
    
    if med.patient_id != patient.id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json() or {}
    status = data.get('status', 'TAKEN').upper()
    log_date_str = data.get('date')
    
    if status not in ['TAKEN', 'MISSED', 'SKIPPED']:
        return jsonify({'error': 'Invalid status'}), 400
        
    if log_date_str:
        log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
    else:
        log_date = datetime.utcnow().date()
        
    # Check if a log entry already exists for that day
    log_entry = MedicationLog.query.filter_by(
        medication_id=med.id, 
        log_date=log_date
    ).first()
    
    if not log_entry:
        log_entry = MedicationLog(
            patient_id=patient.id,
            medication_id=med.id,
            log_date=log_date
        )
        db.session.add(log_entry)
        
    log_entry.status = status
    db.session.commit()
    
    # Recalculate adherence
    total_days = (datetime.utcnow().date() - med.start_date).days + 1
    total_days = max(1, total_days)
    taken_count = MedicationLog.query.filter_by(medication_id=med.id, status='TAKEN').count()
    new_adherence = round((taken_count / total_days) * 100)
    
    return jsonify({
        'success': True, 
        'status': status, 
        'date': log_date.strftime('%Y-%m-%d'),
        'new_adherence': new_adherence
    })
