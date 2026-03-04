# 🌸 Bloom — Period & Wellness Tracker

> *Your cycle, beautifully understood.*

Bloom replaces Flow with better data management, a living garden interface, and a modern design.

---

## Features

- 🔐 **User Authentication** — register/login with full account creation
- 🌿 **Garden Interface** — plants unlock and grow as you track consistently
- 📅 **Smart Calendar** — day / week / month views with period predictions highlighted
- 🌹 **Cycle Tracking** — log periods, predict future ones, track flow & symptoms
- ♡ **Daily Check-ins** — mood, energy, pain level, symptoms, journal notes
- ✓ **Habit Tracking** — custom daily habits with streaks & progress
- 📊 **Bloom Points** — gamified score system that grows your garden

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 + Flask |
| Database | PostgreSQL (psycopg2) |
| Frontend | Jinja2 templates + Vanilla JS |
| Auth | Werkzeug password hashing + Flask sessions |
| Config | python-dotenv (.env file) |

---

## Setup

### 1. Clone and create virtualenv

```bash
git clone <your-repo>
cd bloom
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your credentials
```

Your `.env` file should look like:
```
DB_NAME=bloom
DB_USER=bloomuser
DB_PASSWORD=your_password_here
DB_HOST=your_host_here
DB_PORT=5432
SECRET_KEY=your-very-secret-key
FLASK_ENV=development
```

> ⚠️ **Never commit `.env` to git!** It's in `.gitignore` already.

### 4. Initialize the database

The database tables are created automatically when you start the app for the first time.

### 5. Run

```bash
python app.py
```

App runs at **http://localhost:5000**

---

## Garden Points System

| Action | Points |
|---|---|
| Log a period cycle | +10 pts |
| Daily check-in | +3 pts |
| Complete a habit | +2 pts |

### Plant Milestones

| Plant | Points Required |
|---|---|
| 🌱 Seedling | 0 (sign-up gift) |
| 🌼 Daisy | 10 |
| 🌹 Rose | 25 |
| 🌻 Sunflower | 50 |
| 💜 Lavender | 100 |
| 🌸 Cherry Blossom | 150 |
| 🪷 Lotus | 200 |

---

## Database Schema

```
users          — accounts, cycle settings, contraceptive info
periods        — logged period start/end with flow intensity
habits         — user-defined daily habits
habit_logs     — daily habit completion records
checkins       — daily mood/energy/pain/symptom logs
garden_items   — unlocked plants with growth stages
```

---

## Security Notes

- Passwords hashed with Werkzeug (PBKDF2-HMAC-SHA256)
- Session-based auth with secret key from `.env`
- `.env` excluded from git via `.gitignore`
- SQL uses parameterized queries (psycopg2) — no SQL injection risk
