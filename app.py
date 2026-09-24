import os
from app import create_app, db

app = create_app()

if __name__ == '__main__':
    # Ensure database tables exist for local testing
    with app.app_context():
        db.create_all()
        print("Database tables initialized successfully.")
        
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    
    # Default debug to False/0 unless explicitly set to '1' or 'true'
    flask_debug_env = os.environ.get('FLASK_DEBUG', '0').lower()
    debug = flask_debug_env in ('1', 'true')
    
    if debug:
        import logging
        logging.warning("WARNING: Debug mode is active. Sensitive debug pages and debug endpoints are exposed to the network!")
        
    app.run(host=host, port=port, debug=debug)
