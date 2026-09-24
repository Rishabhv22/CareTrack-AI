# SQLite to PostgreSQL Migration Guide

CareTrack AI supports SQLite as the default database for local development, and PostgreSQL for staging/production deployments. This document details the database migration path using the existing Flask-Migrate/Alembic setup.

---

## 🛠️ PostgreSQL Compatibility Configuration

The database URI configuration in `config.py` automatically handles PostgreSQL URIs (including mapping older `postgres://` schemes to modern `postgresql://` prefixes):

```python
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    # Fix for Heroku/AWS RDS PostgreSQL url configuration changes
    db_url = db_url.replace("postgres://", "postgresql://", 1)

SQLALCHEMY_DATABASE_URI = db_url or f"sqlite:///{basedir / 'instance' / 'caretrack.db'}"
```

---

## 🚀 Migration Steps for Production Deployments

Follow these steps to deploy and migrate the database schema to a PostgreSQL instance:

### Step 1: Install PostgreSQL Client Library
Ensure `psycopg2-binary` (or `psycopg2`) is installed in your python environment. Add it to the production requirements:
```bash
pip install psycopg2-binary
```

### Step 2: Configure Environment Variables
Define the database connection string via the `DATABASE_URL` environment variable:
```bash
export DATABASE_URL="postgresql://username:password@hostname:5432/dbname"
```

### Step 3: Run Database Migrations
Since the migrations folder is tracked in version control, you only need to run the upgrade command on the target environment to instantiate the full schema:
```bash
flask db upgrade
```
Alembic will automatically connect to the database specified in `DATABASE_URL`, detect it is a PostgreSQL instance, and run the SQL generation scripts sequentially up to the latest revision.

### Step 4: Verify Migration Status
Confirm the database status and matching schema version:
```bash
flask db current
```
This should output the latest revision ID: `6c7d5e3b7a3d (head)`.
