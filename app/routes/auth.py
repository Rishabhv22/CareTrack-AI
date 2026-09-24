from urllib.parse import urlparse
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
from app.extensions import db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.recommendation import AuditLog

auth_bp = Blueprint('auth', __name__)

# Forms
class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Log In')

class RegistrationForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=10, message='Password must be at least 10 characters long.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match.')
    ])
    role = SelectField('Register As', choices=[
        ('PATIENT', 'Patient (Chronic Care Monitoring)'),
        ('DOCTOR', 'Healthcare Professional (Doctor)')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Account')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('This email address is already registered.')

    def validate_password(self, password):
        data = password.data
        if not any(c.isdigit() for c in data) or not any(c.isalpha() for c in data):
            raise ValidationError('Password must contain at least one letter and one number.')

# Routes
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            role=form.role.data.upper()
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        # Log action
        audit = AuditLog(user_id=user.id, action="REGISTER", ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()
        
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'PATIENT':
            return redirect(url_for('patient.dashboard'))
        elif current_user.role == 'DOCTOR':
            return redirect(url_for('doctor.dashboard'))
        elif current_user.role == 'ADMIN':
            return redirect(url_for('doctor.admin_dashboard'))
            
    form = LoginForm()
    if form.validate_on_submit():
        email_attempt = form.email.data.lower()
        ip_addr = request.remote_addr
        
        # Check failed attempts in the last 15 minutes
        time_limit = datetime.utcnow() - timedelta(minutes=15)
        failed_count = AuditLog.query.filter(
            AuditLog.timestamp >= time_limit,
            AuditLog.action.like('LOGIN_FAILED%'),
            ((AuditLog.ip_address == ip_addr) | (AuditLog.action == f"LOGIN_FAILED email={email_attempt}"))
        ).count()
        
        if failed_count >= 5:
            flash('Too many failed login attempts. Please try again in 15 minutes.', 'danger')
            return render_template('auth/login.html', form=form)
            
        user = User.query.filter_by(email=email_attempt).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'danger')
                return redirect(url_for('auth.login'))
                
            login_user(user, remember=form.remember.data)
            # session.permanent = True activates PERMANENT_SESSION_LIFETIME; remember=True controls persistent remember-me cookie behavior.
            session.permanent = True
            
            # Log action
            audit = AuditLog(user_id=user.id, action="LOGIN", ip_address=ip_addr)
            db.session.add(audit)
            db.session.commit()
            
            # Check if profile exists; if not, redirect to profile completion
            if user.role == 'PATIENT' and not user.patient_profile:
                flash('Please complete your patient profile to continue.', 'info')
                return redirect(url_for('patient.create_profile'))
            elif user.role == 'DOCTOR' and not user.doctor_profile:
                flash('Please complete your clinician profile to continue.', 'info')
                return redirect(url_for('doctor.create_profile'))
                
            next_page = request.args.get('next')
            if next_page:
                parsed_url = urlparse(next_page)
                # Same-origin relative path check: no scheme/netloc, and not protocol-relative
                if not (parsed_url.scheme or parsed_url.netloc) and not next_page.startswith('//'):
                    return redirect(next_page)
                
            if user.role == 'PATIENT':
                return redirect(url_for('patient.dashboard'))
            elif user.role == 'DOCTOR':
                return redirect(url_for('doctor.dashboard'))
            elif user.role == 'ADMIN':
                return redirect(url_for('doctor.admin_dashboard'))
        else:
            # Log failed attempt
            target_user_id = user.id if user else None
            audit_fail = AuditLog(
                user_id=target_user_id,
                action=f"LOGIN_FAILED email={email_attempt}",
                ip_address=ip_addr
            )
            db.session.add(audit_fail)
            db.session.commit()
            
            flash('Invalid email or password. Please try again.', 'danger')
            
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    audit = AuditLog(user_id=current_user.id, action="LOGOUT", ip_address=request.remote_addr)
    db.session.add(audit)
    db.session.commit()
    
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
