import os
from flask import Flask, render_template
from config import Config
from app.extensions import db, migrate, login_manager, csrf

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extension config
    config_class.init_app(app)
    
    # Log warning if debug mode is active
    if app.debug:
        app.logger.warning("WARNING: Debug mode is active. Sensitive debug pages and debug endpoints are exposed to the network!")
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Secure Headers via Flask-Talisman
    from flask_talisman import Talisman
    csp_policy = {
        'default-src': '\'self\'',
        'script-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'https://cdn.jsdelivr.net'
        ],
        'style-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'https://fonts.googleapis.com',
            'https://cdn.jsdelivr.net'
        ],
        'font-src': [
            '\'self\'',
            'https://fonts.gstatic.com',
            'https://cdn.jsdelivr.net'
        ],
        'img-src': [
            '\'self\'',
            'data:'
        ]
    }
    is_debug_or_test = app.debug or app.testing
    Talisman(
        app,
        content_security_policy=csp_policy,
        force_https=not is_debug_or_test,
        strict_transport_security=not is_debug_or_test
    )
    
    # Setup login configurations
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        # Using Session.get() as recommended in SQLAlchemy 2.0+
        return db.session.get(User, user_id)
        
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.patient import patient_bp
    from app.routes.doctor import doctor_bp
    from app.routes.reports import reports_bp
    from app.routes.medication import medication_bp
    from app.routes.ai import ai_bp
    from app.routes.wearables import wearables_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(patient_bp, url_prefix='/patient')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(medication_bp, url_prefix='/medication')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(wearables_bp, url_prefix='/')
    
    # Root redirect / landing page
    @app.route('/')
    def index():
        from flask import current_app, redirect, url_for
        from flask_login import current_user
        
        if current_user.is_authenticated:
            if current_user.role == 'PATIENT':
                return redirect(url_for('patient.dashboard'))
            elif current_user.role == 'DOCTOR':
                return redirect(url_for('doctor.dashboard'))
            elif current_user.role == 'ADMIN':
                return redirect(url_for('doctor.admin_dashboard'))
                
        return render_template('landing.html')
        
    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
        
    @app.errorhandler(Exception)
    def handle_exception(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            # Pass through standard HTTP exceptions
            return e
            
        db.session.rollback()
        from flask import request
        import sys
        exc_type, _, _ = sys.exc_info()
        exc_name = exc_type.__name__ if exc_type else "Exception"
        app.logger.error(f"Sanitized Unhandled Exception: {exc_name} occurred on route {request.path} (method: {request.method})")
        return render_template('errors/500.html'), 500

    # Healthcare safety inject context processor
    @app.context_processor
    def inject_disclaimer():
        return {
            'healthcare_disclaimer': (
                "CareTrack AI provides monitoring and informational support and does "
                "not replace professional medical advice, diagnosis, or treatment."
            )
        }
        
    return app
