# ConnectSphere-Event-Services

## Project layout

```
connectsphere/
├── backend/        # Flask REST API
├── frontend/       # Vue 3 + Vite single-page app
├── database/
│   └── schema.sql  # MySQL DDL — run this once to create the database
└── .gitignore
```

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- MySQL 8.0+
- (Optional) `virtualenv` for isolating Python dependencies

## 1. Database setup

1. Create the database and a user for it:

   ```sql
   CREATE DATABASE connectsphere CHARACTER SET utf8mb4;
   CREATE USER 'connectsphere_user'@'localhost' IDENTIFIED BY 'password';
   GRANT ALL PRIVILEGES ON connectsphere.* TO 'connectsphere_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

2. Load the schema:

   ```bash
   mysql -u connectsphere_user -p connectsphere < database/schema.sql
   ```

   This creates all tables and seeds the five fixed roles (`event_organiser`,
   `event_coordinator`, `venue_staff`, `technical_support_staff`,
   `attendee`).

## 2. Backend setup (Flask API)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL to match the DB user/password you created above
```

Since ConnectSphere accounts are provisioned outside the system (Event
Organisers, Attendees) or created directly by ConnectSphere (internal
staff), there is no self-registration endpoint yet. Seed a set of test
users for local development instead:

```bash
python scripts/seed_users.py
```

This creates one user per role (`organiser@example.com`,
`coordinator1@example.com`, `coordinator2@example.com`, `venue@example.com`,
`techsupport@example.com`, `attendee@example.com`), all with the password
`Password123!`.

The seed script now also creates sample venues `Main Auditorium`, `Seminar Room A` and `Banquet Hall`.

Run the API:

```bash
python run.py
```

The API listens on `http://localhost:5000/api`.

### Venue Suitability Check

Seed sample venues with `python scripts/seed_venues.py`. If your database was
created from this branch before the feature existed, apply
`database/migrations/001_venue_suitability.sql` first. See
[VENUE_SUITABILITY.md](VENUE_SUITABILITY.md) for the rules and API.

### Running tests

```bash
pip install pytest
pytest
```

### Continuous integration (CI gate)

`.github/workflows/tests.yml` runs on every push to `main` and every pull
request into `main`. It has two jobs, `test` (backend `pytest`) and
`frontend-build` (`npm ci && npm run build`). To make them a gate that blocks
merging, go to **Settings → Rules → Rulesets → New branch ruleset** (or
**Settings → Branches → Add classic branch protection rule**), target `main`, and turn on:

1. **Require a pull request before merging** (leave *Required approvals* at 0
   if you merge your own PRs).
2. **Require status checks to pass**, adding `test` and `frontend-build` — they
   only appear in the search box after the workflow has run once.
3. **Block force pushes** (on by default for rulesets).

Optional local check before pushing: `git config core.hooksPath .githooks`
installs a pre-push hook that runs the backend tests.

## 3. Frontend setup (Vue)

```bash
cd frontend
npm install
cp .env.example .env
# edit .env if your backend isn't on http://localhost:5000/api
npm run dev
```

The app is served at `http://localhost:5173`. Log in with any of the seeded
test accounts above.

## 4. Typical local workflow

1. Start MySQL and confirm the schema is loaded.
2. In one terminal: `cd backend && source venv/bin/activate && python run.py`
3. In another terminal: `cd frontend && npm run dev`
4. Open `http://localhost:5173`, log in as `organiser@example.com` to create
   and submit an event request, then log in as `coordinator1@example.com` (or
   `coordinator2@example.com`, whichever the system auto-assigned) to review,
   request clarification, approve, or reject it.
