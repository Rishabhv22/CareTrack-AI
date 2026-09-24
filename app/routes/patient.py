from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, SelectField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired, NumberRange, Length, Optional
from app.extensions import db
from app.models.patient import Patient
from app.models.recommendation import AuditLog
from app.services.bmi_service import calculate_bmi, get_bmi_category, get_bmi_interpretation

patient_bp = Blueprint('patient', __name__)

class PatientProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=0, max=120)])
    gender = SelectField('Gender', choices=[
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
        ('Prefer not to say', 'Prefer not to say')
    ], validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    
    # Measurements
    height = FloatField('Height (cm)', validators=[DataRequired(), NumberRange(min=30, max=300)])
    weight = FloatField('Weight (kg)', validators=[DataRequired(), NumberRange(min=2, max=600)])
    
    # Conditions
    primary_condition = SelectField('Primary Monitored Condition', choices=[
        ('Type 2 Diabetes', 'Type 2 Diabetes'),
        ('Hypertension', 'Hypertension'),
        ('Obesity', 'Obesity'),
        ('High Cholesterol', 'High Cholesterol'),
        ('Heart Disease', 'Heart Disease'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    other_conditions = TextAreaField('Other Conditions / Comorbidities (Optional)')
    allergies = TextAreaField('Known Allergies (Optional)')
    family_history = TextAreaField('Family Medical History (Optional)')
    
    # Lifestyle
    smoking = SelectField('Smoking Status', choices=[
        ('Never', 'Never Smoked'),
        ('Former', 'Former Smoker'),
        ('Active', 'Active Smoker')
    ], validators=[DataRequired()])
    alcohol = SelectField('Alcohol Consumption', choices=[
        ('None', 'None / Teetotaler'),
        ('Occasional', 'Occasional Drinker'),
        ('Regular', 'Regular Drinker')
    ], validators=[DataRequired()])
    sleep_hours = FloatField('Average Sleep Hours per Night', validators=[DataRequired(), NumberRange(min=0, max=24)])
    activity_level = SelectField('Physical Activity Level', choices=[
        ('Sedentary', 'Sedentary (Little/no exercise)'),
        ('Light', 'Light (1-2 days/week)'),
        ('Moderate', 'Moderate (3-4 days/week)'),
        ('Active', 'Active (5+ days/week)')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Save Profile')

@patient_bp.route('/dashboard')
@login_required
def dashboard():
    from datetime import datetime, timedelta
    from app.models.daily_log import DailyHealthLog
    from app.models.medication import Medication
    from app.models.recommendation import AISummary, Notification
    from app.services.compliance_engine import calculate_adherence_score
    
    if current_user.role != 'PATIENT':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    # Check if patient profile exists; if not, force creation
    patient = current_user.patient_profile
    if not patient:
        flash('Please complete your profile to access the dashboard.', 'warning')
        return redirect(url_for('patient.create_profile'))
        
    # Log access
    db.session.add(AuditLog(
        user_id=current_user.id,
        patient_id=patient.id,
        action="VIEW_PATIENT_DASHBOARD",
        ip_address=request.remote_addr
    ))
    db.session.commit()
        
    today = datetime.utcnow().date()
    
    # Calculate adherence score
    adherence = calculate_adherence_score(patient)
    
    # Fetch today's check-in
    today_log = DailyHealthLog.query.filter_by(patient_id=patient.id, log_date=today).first()
    
    # Fetch active medications
    meds = Medication.query.filter_by(patient_id=patient.id, is_active=True).all()
    
    # Fetch latest AI weekly summary
    latest_summary = AISummary.query.filter_by(patient_id=patient.id).order_by(AISummary.created_at.desc()).first()
    
    # Fetch unread notifications
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).all()
    
    # Fetch historical logs for charts (last 30 days)
    start_date = today - timedelta(days=30)
    chart_logs = DailyHealthLog.query.filter(
        DailyHealthLog.patient_id == patient.id,
        DailyHealthLog.log_date >= start_date
    ).order_by(DailyHealthLog.log_date.asc()).all()
    
    # Format chart data
    dates = [log.log_date.strftime('%b %d') for log in chart_logs]
    weights = [log.weight for log in chart_logs if log.weight is not None]
    weight_dates = [log.log_date.strftime('%b %d') for log in chart_logs if log.weight is not None]
    
    glucose = [log.blood_glucose for log in chart_logs if log.blood_glucose is not None]
    glucose_dates = [log.log_date.strftime('%b %d') for log in chart_logs if log.blood_glucose is not None]
    
    bp_sys = [log.systolic_bp for log in chart_logs if log.systolic_bp is not None]
    bp_dia = [log.diastolic_bp for log in chart_logs if log.diastolic_bp is not None]
    bp_dates = [log.log_date.strftime('%b %d') for log in chart_logs if log.systolic_bp is not None]
    
    bmi_category = get_bmi_category(patient.bmi) if patient.bmi else 'N/A'
    bmi_info = get_bmi_interpretation(patient.bmi) if patient.bmi else ''
    
    return render_template(
        'patient/dashboard.html',
        patient=patient,
        bmi_category=bmi_category,
        bmi_info=bmi_info,
        adherence=adherence,
        today_log=today_log,
        meds=meds,
        latest_summary=latest_summary,
        unread_notifications=unread_notifications,
        dates=dates,
        weights=weights,
        weight_dates=weight_dates,
        glucose=glucose,
        glucose_dates=glucose_dates,
        bp_sys=bp_sys,
        bp_dia=bp_dia,
        bp_dates=bp_dates
    )


@patient_bp.route('/profile/create', methods=['GET', 'POST'])
@login_required
def create_profile():
    if current_user.role != 'PATIENT':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    patient = current_user.patient_profile
    form = PatientProfileForm()
    
    # Pre-populate form if patient profile already exists
    if request.method == 'GET' and patient:
        form.name.data = patient.name
        form.age.data = patient.age
        form.gender.data = patient.gender
        form.phone.data = patient.phone
        form.height.data = patient.height
        form.weight.data = patient.weight
        form.primary_condition.data = patient.primary_condition
        form.other_conditions.data = patient.other_conditions
        form.allergies.data = patient.allergies
        form.family_history.data = patient.family_history
        form.smoking.data = patient.smoking
        form.alcohol.data = patient.alcohol
        form.sleep_hours.data = patient.sleep_hours
        form.activity_level.data = patient.activity_level
        
    if form.validate_on_submit():
        # Calculate BMI
        bmi_value = calculate_bmi(form.weight.data, form.height.data)
        
        if not patient:
            # Create new profile
            patient = Patient(
                user_id=current_user.id,
                name=form.name.data,
                age=form.age.data,
                gender=form.gender.data,
                phone=form.phone.data,
                height=form.height.data,
                weight=form.weight.data,
                bmi=bmi_value,
                primary_condition=form.primary_condition.data,
                other_conditions=form.other_conditions.data,
                allergies=form.allergies.data,
                family_history=form.family_history.data,
                smoking=form.smoking.data,
                alcohol=form.alcohol.data,
                sleep_hours=form.sleep_hours.data,
                activity_level=form.activity_level.data
            )
            db.session.add(patient)
            flash('Profile completed successfully!', 'success')
        else:
            # Update existing profile
            patient.name = form.name.data
            patient.age = form.age.data
            patient.gender = form.gender.data
            patient.phone = form.phone.data
            patient.height = form.height.data
            patient.weight = form.weight.data
            patient.bmi = bmi_value
            patient.primary_condition = form.primary_condition.data
            patient.other_conditions = form.other_conditions.data
            patient.allergies = form.allergies.data
            patient.family_history = form.family_history.data
            patient.smoking = form.smoking.data
            patient.alcohol = form.alcohol.data
            patient.sleep_hours = form.sleep_hours.data
            patient.activity_level = form.activity_level.data
            flash('Profile updated successfully!', 'success')
            
        db.session.commit()
        return redirect(url_for('patient.dashboard'))
        
    action = "edit" if patient else "create"
    return render_template('patient/profile_form.html', form=form, action=action)

# Daily Check-in Form
class DailyCheckInForm(FlaskForm):
    weight = FloatField('Weight (kg)', validators=[Optional(), NumberRange(min=2, max=600)])
    water_intake = FloatField('Water Intake (Liters)', validators=[Optional(), NumberRange(min=0, max=20)])
    calories = IntegerField('Caloric Intake (kcal)', validators=[Optional(), NumberRange(min=0, max=10000)])
    exercise_duration = IntegerField('Exercise Duration (Minutes)', validators=[Optional(), NumberRange(min=0, max=1440)])
    sleep_hours = FloatField('Hours of Sleep', validators=[Optional(), NumberRange(min=0, max=24)])
    
    # Biomarkers
    blood_glucose = FloatField('Blood Glucose (mg/dL)', validators=[Optional(), NumberRange(min=10, max=1000)])
    systolic_bp = IntegerField('Systolic Blood Pressure (mmHg - top value)', validators=[Optional(), NumberRange(min=50, max=300)])
    diastolic_bp = IntegerField('Diastolic Blood Pressure (mmHg - bottom value)', validators=[Optional(), NumberRange(min=30, max=200)])
    
    # Compliance Checkboxes
    medicine_taken = BooleanField('I took all my prescribed medications today.')
    exercise_completed = BooleanField('I completed my scheduled physical exercise today.')
    diet_followed = BooleanField('I followed my recommended nutrition/diet plan today.')
    
    # Mood and energy
    mood = SelectField('Current Mood', choices=[
        ('Good', 'Good / Positive'),
        ('Neutral', 'Neutral / Stable'),
        ('Low', 'Low / Down')
    ], validators=[DataRequired()])
    energy = SelectField('Energy Level', choices=[
        ('High', 'High / Active'),
        ('Medium', 'Medium / Moderate'),
        ('Low', 'Low / Fatigue')
    ], validators=[DataRequired()])
    
    # Journal and symptoms
    symptoms = TextAreaField('Symptom Notes (Optional)', validators=[Optional(), Length(max=500)])
    journal_text = TextAreaField('Daily Journal / Notes (Optional)', validators=[Optional()])
    
    submit = SubmitField('Submit Check-in')

@patient_bp.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    from datetime import datetime
    from app.models.daily_log import DailyHealthLog
    from app.models.journal import JournalEntry
    from app.models.recommendation import Alert
    from app.services.nlp_service import analyze_journal
    
    if current_user.role != 'PATIENT':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    patient = current_user.patient_profile
    if not patient:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('patient.create_profile'))
        
    today = datetime.utcnow().date()
    
    # Look for existing log for today
    daily_log = DailyHealthLog.query.filter_by(patient_id=patient.id, log_date=today).first()
    journal_entry = JournalEntry.query.filter_by(patient_id=patient.id, entry_date=today).first() if daily_log else None
    
    form = DailyCheckInForm()
    
    # Pre-populate form on GET request
    if request.method == 'GET':
        if daily_log:
            form.weight.data = daily_log.weight
            form.water_intake.data = daily_log.water_intake
            form.calories.data = daily_log.calories
            form.exercise_duration.data = daily_log.exercise_duration
            form.sleep_hours.data = daily_log.sleep_hours
            form.blood_glucose.data = daily_log.blood_glucose
            form.systolic_bp.data = daily_log.systolic_bp
            form.diastolic_bp.data = daily_log.diastolic_bp
            form.medicine_taken.data = daily_log.medicine_taken
            form.exercise_completed.data = daily_log.exercise_completed
            form.diet_followed.data = daily_log.diet_followed
            form.mood.data = daily_log.mood
            form.energy.data = daily_log.energy
            form.symptoms.data = daily_log.symptoms
            
            if journal_entry:
                form.journal_text.data = journal_entry.journal_text
        else:
            # Prefill weight from patient profile
            form.weight.data = patient.weight
            
    if form.validate_on_submit():
        if not daily_log:
            daily_log = DailyHealthLog(
                patient_id=patient.id,
                log_date=today
            )
            db.session.add(daily_log)
            
        # Update daily log fields
        daily_log.weight = form.weight.data
        daily_log.water_intake = form.water_intake.data
        daily_log.calories = form.calories.data
        daily_log.exercise_duration = form.exercise_duration.data
        daily_log.sleep_hours = form.sleep_hours.data
        daily_log.blood_glucose = form.blood_glucose.data
        daily_log.systolic_bp = form.systolic_bp.data
        daily_log.diastolic_bp = form.diastolic_bp.data
        daily_log.medicine_taken = form.medicine_taken.data
        daily_log.exercise_completed = form.exercise_completed.data
        daily_log.diet_followed = form.diet_followed.data
        daily_log.mood = form.mood.data
        daily_log.energy = form.energy.data
        daily_log.symptoms = form.symptoms.data
        
        # Flush to generate daily_log.id for relationship if it's new
        db.session.flush()
        
        # Update/Create Journal Entry and trigger NLP analysis
        if form.journal_text.data:
            nlp_result = analyze_journal(form.journal_text.data)
            
            if not journal_entry:
                journal_entry = JournalEntry(
                    patient_id=patient.id,
                    daily_log_id=daily_log.id,
                    entry_date=today
                )
                db.session.add(journal_entry)
                
            journal_entry.journal_text = form.journal_text.data
            journal_entry.summary = nlp_result["summary"]
            journal_entry.extracted_symptoms = ", ".join(nlp_result["symptoms"])
            journal_entry.extracted_medications = nlp_result["medications"]
            journal_entry.extracted_diet_activity = nlp_result["diet_activity"]
            journal_entry.concerning_flag = nlp_result["concerning_flag"]
            
            # If concerning flag raised, trigger alert for doctor
            if nlp_result["concerning_flag"]:
                existing_alert = Alert.query.filter_by(
                    patient_id=patient.id,
                    alert_type='Symptom',
                    status='ACTIVE'
                ).first()
                if not existing_alert:
                    alert = Alert(
                        patient_id=patient.id,
                        alert_type='Symptom',
                        severity='MEDIUM',
                        message=f"Concerning symptom description reported in daily journal: '{nlp_result['summary']}'"
                    )
                    db.session.add(alert)
        elif journal_entry:
            # If journal text was cleared, delete the journal entry
            db.session.delete(journal_entry)
            
        # Also trigger alert if blood glucose or blood pressure values are abnormally high/low
        # E.g., Glucose > 250 or BP Systolic > 180 (severe hypertension range)
        if form.blood_glucose.data and (form.blood_glucose.data > 250 or form.blood_glucose.data < 60):
            glucose_severity = 'HIGH' if (form.blood_glucose.data > 300 or form.blood_glucose.data < 50) else 'MEDIUM'
            alert_msg = f"Abnormal Blood Glucose recorded: {form.blood_glucose.data} mg/dL (Requires clinician review)."
            existing_g_alert = Alert.query.filter_by(patient_id=patient.id, alert_type='Biometric', status='ACTIVE').first()
            if not existing_g_alert:
                db.session.add(Alert(patient_id=patient.id, alert_type='Biometric', severity=glucose_severity, message=alert_msg))
                
        if form.systolic_bp.data and (form.systolic_bp.data > 160 or form.systolic_bp.data < 90):
            bp_severity = 'HIGH' if form.systolic_bp.data > 180 else 'MEDIUM'
            alert_msg = f"Abnormal Blood Pressure recorded: {form.systolic_bp.data}/{form.diastolic_bp.data or 'N/A'} mmHg (Requires clinician review)."
            existing_bp_alert = Alert.query.filter_by(patient_id=patient.id, alert_type='Biometric', status='ACTIVE').first()
            if not existing_bp_alert:
                db.session.add(Alert(patient_id=patient.id, alert_type='Biometric', severity=bp_severity, message=alert_msg))

        db.session.commit()
        flash('Daily health check-in submitted successfully!', 'success')
        return redirect(url_for('patient.dashboard'))
        
    return render_template('patient/checkin.html', form=form, daily_log=daily_log)
