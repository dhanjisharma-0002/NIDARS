# Deploying NIDARS to Vercel

This guide explains how to deploy **NIDARS** to [Vercel](https://vercel.com/) as a Serverless Python Flask application.

---

## Architecture Overview

On Vercel, NIDARS runs using the **@vercel/python** serverless runtime. Key adaptations in place:
1. **Entry Point**: Routed automatically via [`api/index.py`](api/index.py) and [`vercel.json`](vercel.json).
2. **Bundle Optimization**: Non-runtime assets (raw 65 MB Excel spreadsheets, development caches, testing suites) are excluded via [`.vercelignore`](.vercelignore) to stay well under Vercel's 50 MB (compressed) and 250 MB (uncompressed) serverless limit.
3. **Database Flexibility**:
   - **PostgreSQL** (Supabase, Neon, Vercel Postgres) supported out-of-the-box via `pg8000`.
   - **MySQL** (PlanetScale, Railway, Aiven, Cleardb) supported via `PyMySQL`.
   - **Zero-Config SQLite Fallback** (`/tmp/nidars.db`) automatically activates if no database credentials are provided, allowing immediate preview deployments.
4. **Resilient Filesystem**: Static and user uploads gracefully target the writable `/tmp` directory.
5. **GIS Offline Data**: Bundled with 64 North Indian meteorological stations in [`gis/geojson/stations_latest.json`](gis/geojson/stations_latest.json) so the interactive risk map works immediately upon deployment.

---

## Method 1: Deploy via GitHub (Recommended)

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Configure NIDARS for Vercel serverless deployment"
   git push origin main
   ```

2. **Connect to Vercel**:
   - Navigate to [vercel.com/new](https://vercel.com/new).
   - Sign in with GitHub and select your **NIDARS** repository.

3. **Configure Project Settings**:
   - **Framework Preset**: *Other* (or auto-detected *Flask*).
   - **Root Directory**: `./` (leave default).

4. **Add Environment Variables** *(Optional for preview; Recommended for production)*:
   Expand **Environment Variables** and provide:

   | Variable | Example Value | Description |
   | :--- | :--- | :--- |
   | `SECRET_KEY` | *(Generate a 32+ character random string)* | Required for session security and CSRF protection. |
   | `FLASK_ENV` | `production` | Enables production security flags. |
   | `DATABASE_URL` | `postgresql://user:pass@ep-xyz.aws.neon.tech/neondb?sslmode=require` | External database (PostgreSQL or MySQL). |

   *(Note: If `DATABASE_URL` is omitted, the app will use the zero-config SQLite database in `/tmp`).*

5. **Deploy**:
   Click **Deploy**. Vercel will install dependencies from `requirements.txt` and launch your serverless app.

---

## Method 2: Deploy via Vercel CLI

1. **Install Vercel CLI** (if not already installed):
   ```bash
   npm install -g vercel
   ```

2. **Log In to Vercel**:
   ```bash
   vercel login
   ```

3. **Deploy Preview**:
   Run from the project root:
   ```bash
   vercel
   ```
   Follow the interactive prompts (defaults are pre-configured).

4. **Deploy to Production**:
   ```bash
   vercel --prod
   ```

---

## Connecting a Production Database

### Option A: Neon / Supabase / Vercel Postgres (Recommended)
1. Create a free database on [Neon](https://neon.tech/) or [Supabase](https://supabase.com/).
2. Copy the Connection String URI (e.g. `postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require`).
3. Add it as `DATABASE_URL` in your Vercel Project Settings under **Settings > Environment Variables**.
4. NIDARS automatically detects `postgresql://` and routes queries via the pure-Python `pg8000` driver.

### Option B: PlanetScale / Aiven / Railway (MySQL)
1. Create a MySQL database instance.
2. Provide either:
   - `DATABASE_URL`: `mysql+pymysql://user:pass@host:port/dbname?charset=utf8mb4`
   - Or separate variables: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `DB_NAME`.

---

## Verifying Deployment Health

Once deployed, you can verify your service status via the built-in health endpoint:
```
https://<your-deployment-url>.vercel.app/api/health
```

Expected JSON response:
```json
{
  "application": "NIDARS",
  "database": "connected",
  "database_name": "...",
  "message": "Application is running",
  "phase": 3,
  "status": "running"
}
```

Visit the interactive map at `https://<your-deployment-url>.vercel.app/map` to test geospatial risk scoring.
