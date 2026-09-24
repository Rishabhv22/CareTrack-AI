import os
from app import create_app, db

app = create_app()

with app.app_context():
    # Ensure all database tables exist
    db.create_all()
    
    try:
        from app.models.user import User
        if User.query.count() == 0:
            print("No existing users found. Seeding initial demo data for deployment...")
            from scripts.seed_database import seed_database
            seed_database()
            print("Demo database initialized successfully.")
        else:
            print(f"Database already initialized with {User.query.count()} user(s).")
    except Exception as e:
        print("Database initialization notice:", e)

print("Pre-flight database setup complete.")
