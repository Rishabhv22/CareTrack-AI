import os
from app import create_app, db

app = create_app()

# Initialize tables and seed demo data on startup (runs under both Gunicorn and dev server)
with app.app_context():
    db.create_all()
    try:
        from app.models.user import User
        if User.query.count() == 0:
            print("Database is empty. Seeding initial demo data...")
            from scripts.seed_database import seed_database
            seed_database()
            print("Demo database initialized successfully.")
    except Exception as e:
        print("Initial database check/seed notice:", e)

if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    
    # Default debug to False/0 unless explicitly set to '1' or 'true'
    flask_debug_env = os.environ.get('FLASK_DEBUG', '0').lower()
    debug = flask_debug_env in ('1', 'true')
    
    if debug:
        import logging
        logging.warning("WARNING: Debug mode is active. Sensitive debug pages and debug endpoints are exposed to the network!")
        
    app.run(host=host, port=port, debug=debug)
