from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    try:
        from app.models.user import User
        if User.query.count() == 0:
            print("Seeding initial demo data for production deployment...")
            from scripts.seed_database import seed_database
            seed_database()
            print("Demo database initialized successfully.")
    except Exception as e:
        print("Startup database check/seed notice:", e)

if __name__ == '__main__':
    app.run()
