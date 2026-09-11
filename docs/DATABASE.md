# NIDARS — Database Schema & Architecture

**Database Engine:** MySQL 8.0  
**ORM:** Flask-SQLAlchemy (SQLAlchemy 2.0)  
**Migration Tool:** Flask-Migrate / Alembic  
**Target Schema:** `nidars_db`

---

## 1. Entity-Relationship Model

```text
               ┌───────────────────────────┐
               │           users           │
               ├───────────────────────────┤
               │ id (PK)                   │
               │ email (Unique)            │
               │ password_hash             │
               │ name                      │
               │ role ('user', 'admin')    │
               │ created_at                │
               └─────────────┬─────────────┘
                             │ 1
                             │
                             │ N
               ┌─────────────▼─────────────┐          ┌───────────────────────────┐
               │    prediction_history     │          │         locations         │
               ├───────────────────────────┤          ├───────────────────────────┤
               │ id (PK)                   │    N   1 │ id (PK)                   │
               │ user_id (FK) ─────────────┼──────────┤ name                      │
               │ location_id (FK) ─────────┼──────────┤ latitude                  │
               │ prediction_type           │          │ longitude                 │
               │ status                    │          │ state                     │
               │ result_json               │          │ district                  │
               │ created_at                │          │ created_at                │
               └───────────────────────────┘          └───────────────────────────┘

               ┌───────────────────────────┐          ┌───────────────────────────┐
               │   emergency_facilities    │          │    emergency_requests     │
               ├───────────────────────────┤          ├───────────────────────────┤
               │ id (PK)                   │          │ id (PK)                   │
               │ name                      │          │ user_id (FK -> users.id)  │
               │ facility_type (hospital,  │          │ latitude                  │
               │   police, shelter)        │          │ longitude                 │
               │ latitude, longitude       │          │ request_type              │
               │ address, phone            │          │ facility_type             │
               │ opening_hours, source     │          │ risk_level                │
               │ external_id (OSM ID)      │          │ flood_probability         │
               │ is_active, created_at     │          │ landslide_probability     │
               └───────────────────────────┘          │ result_summary, created_at│
                                                      └───────────────────────────┘
```

---

## 2. Table Schemas & Indexes

### Table: `users`
* `id` INT AUTO_INCREMENT PRIMARY KEY
* `email` VARCHAR(255) NOT NULL UNIQUE (Index)
* `password_hash` VARCHAR(255) NOT NULL
* `name` VARCHAR(150) NOT NULL
* `role` VARCHAR(20) NOT NULL DEFAULT 'user' (Index)
* `created_at` DATETIME NOT NULL

### Table: `locations`
* `id` INT AUTO_INCREMENT PRIMARY KEY
* `name` VARCHAR(150) NOT NULL
* `latitude` DECIMAL(9,6) NOT NULL
* `longitude` DECIMAL(9,6) NOT NULL
* `state` VARCHAR(100) NOT NULL (Index)
* `district` VARCHAR(100) NOT NULL (Index)
* `created_at` DATETIME NOT NULL

### Table: `prediction_history`
* `id` INT AUTO_INCREMENT PRIMARY KEY
* `user_id` INT NULL (Foreign Key -> `users.id`, Index)
* `location_id` INT NULL (Foreign Key -> `locations.id`, Index)
* `prediction_type` VARCHAR(32) NOT NULL (Index)
* `status` VARCHAR(32) NOT NULL DEFAULT 'queued'
* `result_json` JSON NULL
* `created_at` DATETIME NOT NULL

### Table: `emergency_facilities`
* `id` INT AUTO_INCREMENT PRIMARY KEY
* `name` VARCHAR(200) NOT NULL
* `facility_type` VARCHAR(50) NOT NULL (Index: `idx_fac_type_lat_lon`)
* `latitude` DECIMAL(9,6) NOT NULL (Index: `idx_fac_type_lat_lon`)
* `longitude` DECIMAL(9,6) NOT NULL (Index: `idx_fac_type_lat_lon`)
* `address` VARCHAR(300) NULL
* `phone` VARCHAR(80) NULL
* `opening_hours` VARCHAR(150) NULL
* `source` VARCHAR(100) NOT NULL DEFAULT 'OpenStreetMap'
* `external_id` VARCHAR(100) NULL (Index: `idx_fac_external_id`)
* `is_active` BOOLEAN NOT NULL DEFAULT TRUE
* `created_at` DATETIME NOT NULL
* `updated_at` DATETIME NOT NULL

### Table: `emergency_requests`
* `id` INT AUTO_INCREMENT PRIMARY KEY
* `user_id` INT NULL (Foreign Key -> `users.id`, Index: `idx_em_req_user_created`)
* `latitude` DECIMAL(9,6) NOT NULL
* `longitude` DECIMAL(9,6) NOT NULL
* `request_type` VARCHAR(50) NOT NULL (Index: `idx_em_req_type_created`)
* `facility_type` VARCHAR(50) NULL
* `risk_level` VARCHAR(50) NULL
* `flood_probability` FLOAT NULL
* `landslide_probability` FLOAT NULL
* `result_summary` JSON NULL
* `created_at` DATETIME NOT NULL (Index: `idx_em_req_type_created`)

---

## 3. Database Migrations & Upgrades

Alembic revisions are tracked in `migrations/versions/`:
* `001_initial_schema.py`: Initial schema creation (`users`, `locations`, `prediction_history`).
* `002_phase7_emergency_tables.py`: Phase 7 schema upgrade (`emergency_facilities`, `emergency_requests`).

### Applying Migrations:
```cmd
.\venv\Scripts\python.exe app.py db-upgrade
```

---

## 4. Backup & Restore Procedures

### Database Backup (mysqldump):
To generate a complete, safe logical backup of `nidars_db`:
```cmd
mysqldump -u root -p --single-transaction --routines --triggers nidars_db > nidars_db_backup.sql
```

### Database Restore:
To restore the database from a backup file:
```cmd
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS nidars_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p nidars_db < nidars_db_backup.sql
```
