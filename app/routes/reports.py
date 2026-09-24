import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.medical_report import MedicalReport, LabResult
from app.models.recommendation import AuditLog
from app.services.ocr_service import extract_text_from_file
from app.services.report_analyzer import extract_parameters

reports_bp = Blueprint('reports', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@reports_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if current_user.role not in ['PATIENT', 'DOCTOR']:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    patient = current_user.patient_profile if current_user.role == 'PATIENT' else None
    
    # If clinician is uploading, they must provide the patient_id as a parameter
    patient_id = request.args.get('patient_id')
    if current_user.role == 'DOCTOR':
        if not patient_id:
            flash('Clinician must select a patient before uploading a report.', 'warning')
            return redirect(url_for('doctor.dashboard'))
        from app.models.patient import Patient
        patient = db.session.get(Patient, patient_id)
        doctor = current_user.doctor_profile
        if not patient or patient not in doctor.patients:
            flash('Access denied. Patient is not assigned to you.', 'danger')
            return redirect(url_for('doctor.dashboard'))

    if request.method == 'POST':
        if 'report_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['report_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to prevent namespace clashes
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            saved_filename = f"{timestamp}_{filename}"
            
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER_PATH'], saved_filename)
            file.save(upload_path)
            
            # Create MedicalReport in database
            report = MedicalReport(
                patient_id=patient.id,
                file_name=filename,
                file_path=upload_path,
                uploaded_by_id=current_user.id
            )
            db.session.add(report)
            db.session.commit()
            
            # Run OCR and text extraction
            raw_text = extract_text_from_file(upload_path)
            report.raw_text = raw_text
            db.session.commit()
            
            # Run parameter extraction
            extracted = extract_parameters(raw_text)
            
            # Save temporary lab results for review
            for item in extracted:
                lab = LabResult(
                    report_id=report.id,
                    patient_id=patient.id,
                    parameter_name=item['parameter_name'],
                    parameter_value=item['parameter_value'],
                    unit=item['unit'],
                    normal_range=item['normal_range'],
                    confidence=item.get('confidence', 95.0)
                )
                db.session.add(lab)
                
            db.session.commit()
            
            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action=f"UPLOAD_REPORT patient_id={patient.id} report_id={report.id}",
                ip_address=request.remote_addr
            )
            db.session.add(audit)
            db.session.commit()
            
            flash('Report uploaded successfully! Please review the extracted lab values.', 'success')
            return redirect(url_for('reports.review', report_id=report.id))
        else:
            flash('Invalid file format. Allowed formats: PDF, PNG, JPG, JPEG.', 'danger')
            
    return render_template('reports/upload.html', patient=patient)

@reports_bp.route('/review/<report_id>', methods=['GET', 'POST'])
@login_required
def review(report_id):
    # Using Session.get() as recommended in SQLAlchemy 2.0+
    report = db.session.get(MedicalReport, report_id)
    if not report:
        flash('Report not found.', 'danger')
        return redirect(url_for('index'))
        
    # Check permissions
    if current_user.role == 'PATIENT' and report.patient_id != current_user.patient_profile.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    if current_user.role == 'DOCTOR':
        doctor = current_user.doctor_profile
        if report.patient not in doctor.patients:
            flash('Access denied. This patient is not assigned to you.', 'danger')
            return redirect(url_for('doctor.dashboard'))
            
    # Log access
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=report.patient_id,
        action="VIEW_REPORT_REVIEW",
        ip_address=request.remote_addr
    ))
    db.session.commit()
        
    if request.method == 'POST':
        # Retrieve all parameters from the form submission
        param_names = request.form.getlist('param_name[]')
        param_values = request.form.getlist('param_value[]')
        param_units = request.form.getlist('param_unit[]')
        param_ranges = request.form.getlist('param_range[]')
        test_date_str = request.form.get('test_date', datetime.utcnow().strftime('%Y-%m-%d'))
        test_date = datetime.strptime(test_date_str, '%Y-%m-%d').date()
        
        # Get server-stored temporary lab results to retrieve untampered confidence values
        temp_results = LabResult.query.filter_by(report_id=report.id).all()
        temp_confidence_map = {res.parameter_name: res.confidence for res in temp_results}
        
        # Clear existing temp results for this report
        LabResult.query.filter_by(report_id=report.id).delete()
        
        # Insert reviewed parameters
        for i in range(len(param_names)):
            if not param_names[i] or not param_values[i]:
                continue
            try:
                val = float(param_values[i])
                
                # Fetch confidence value from server-stored mapping, defaulting to 0.0 if missing/unmatched
                confidence_val = temp_confidence_map.get(param_names[i], 0.0)
                if confidence_val is None:
                    confidence_val = 0.0
                
                # Enforce low confidence confirmation gate
                if confidence_val < 85.0:
                    confirmed_params = request.form.getlist('param_confirmed[]')
                    if param_names[i] not in confirmed_params:
                        flash(f"Parameter '{param_names[i]}' has low confidence and must be explicitly confirmed.", "danger")
                        db.session.rollback()
                        lab_results = LabResult.query.filter_by(report_id=report.id).all()
                        today_str = datetime.utcnow().strftime('%Y-%m-%d')
                        return render_template(
                            'reports/review.html',
                            report=report,
                            lab_results=lab_results,
                            today_str=today_str
                        )
                
                lab = LabResult(
                    report_id=report.id,
                    patient_id=report.patient_id,
                    parameter_name=param_names[i],
                    parameter_value=val,
                    unit=param_units[i],
                    normal_range=param_ranges[i],
                    test_date=test_date,
                    confidence=confidence_val
                )
                db.session.add(lab)
            except ValueError:
                flash(f"Invalid numeric value for {param_names[i]} ignored.", 'warning')
                
        report.is_processed = True
        db.session.commit()
        
        # Check if the weight was updated; if so, update the patient's current profile weight and BMI
        weight_result = LabResult.query.filter_by(report_id=report.id, parameter_name='Weight').first()
        if weight_result:
            patient = report.patient
            patient.weight = weight_result.parameter_value
            # Recalculate BMI
            from app.services.bmi_service import calculate_bmi
            patient.bmi = calculate_bmi(patient.weight, patient.height)
            db.session.commit()
            
        flash('Report analysis reviewed and saved successfully!', 'success')
        
        if current_user.role == 'PATIENT':
            return redirect(url_for('reports.history'))
        else:
            return redirect(url_for('doctor.patient_detail', patient_id=report.patient_id))
            
    # GET request - load results
    lab_results = LabResult.query.filter_by(report_id=report.id).all()
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    
    return render_template(
        'reports/review.html', 
        report=report, 
        lab_results=lab_results,
        today_str=today_str
    )

@reports_bp.route('/history')
@login_required
def history():
    if current_user.role != 'PATIENT':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    patient = current_user.patient_profile
    if not patient:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('patient.create_profile'))
        
    reports = MedicalReport.query.filter_by(patient_id=patient.id, is_processed=True).order_by(MedicalReport.uploaded_at.desc()).all()
    
    # Generate historical trends for key parameters
    target_params = ['HbA1c', 'Fasting Glucose', 'Total Cholesterol', 'LDL Cholesterol', 'Systolic BP', 'Diastolic BP']
    trends = {}
    
    for param in target_params:
        # Fetch last 5 records of this parameter in chronological order
        records = LabResult.query.filter_by(
            patient_id=patient.id,
            parameter_name=param
        ).order_by(LabResult.test_date.asc()).all()
        
        if len(records) >= 2:
            prev = records[-2]
            latest = records[-1]
            diff = round(latest.parameter_value - prev.parameter_value, 2)
            pct = round((diff / prev.parameter_value) * 100, 1) if prev.parameter_value != 0 else 0
            
            trends[param] = {
                'has_trend': True,
                'prev_value': prev.parameter_value,
                'latest_value': latest.parameter_value,
                'diff': diff,
                'pct': pct,
                'unit': latest.unit,
                'chart_data': [{'date': r.test_date.strftime('%b %Y'), 'val': r.parameter_value} for r in records]
            }
        elif len(records) == 1:
            trends[param] = {
                'has_trend': False,
                'latest_value': records[0].parameter_value,
                'unit': records[0].unit,
                'chart_data': [{'date': records[0].test_date.strftime('%b %Y'), 'val': records[0].parameter_value}]
            }
            
    return render_template('reports/history.html', reports=reports, trends=trends)
