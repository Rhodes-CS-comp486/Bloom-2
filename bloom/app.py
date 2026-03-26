from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import psycopg2
import psycopg2.extras
import os
import json
import math

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.getenv('SECRET_KEY', 'bloom-dev-secret')

# ── DB helper ──────────────────────────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            birth_date DATE,
            cycle_length INTEGER DEFAULT 28,
            period_length INTEGER DEFAULT 5,
            last_period_date DATE,
            typical_symptoms TEXT[],
            contraceptive_method VARCHAR(100),
            trying_to_conceive BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS periods (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            start_date DATE NOT NULL,
            end_date DATE,
            flow_intensity VARCHAR(20),
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            frequency VARCHAR(20) DEFAULT 'daily',
            color VARCHAR(7) DEFAULT '#86b49c',
            icon VARCHAR(50) DEFAULT '✿',
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id SERIAL PRIMARY KEY,
            habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            log_date DATE NOT NULL,
            completed BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(habit_id, log_date)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            checkin_date DATE NOT NULL,
            mood INTEGER CHECK (mood >= 1 AND mood <= 5),
            energy INTEGER CHECK (energy >= 1 AND energy <= 5),
            pain_level INTEGER CHECK (pain_level >= 0 AND pain_level <= 5),
            symptoms TEXT[],
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, checkin_date)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS garden_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            plant_type VARCHAR(50) NOT NULL,
            growth_stage INTEGER DEFAULT 1 CHECK (growth_stage >= 1 AND growth_stage <= 5),
            position_x FLOAT DEFAULT 50.0,
            position_y FLOAT DEFAULT 50.0,
            earned_at TIMESTAMP DEFAULT NOW(),
            last_watered TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(100) NOT NULL DEFAULT 'Recommendation',
            message TEXT NOT NULL,
            category VARCHAR(50),
            status VARCHAR(20) NOT NULL DEFAULT 'unread'
                CHECK (status IN ('unread', 'accepted', 'modified', 'dismissed')),
            modified_message TEXT,
            dismissible BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            responded_at TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

def migrate_db():
    """Safely add new columns to existing tables."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE habits ADD COLUMN IF NOT EXISTS paused BOOLEAN DEFAULT FALSE")
        conn.commit()
    except Exception as e:
        print(f"Migration note: {e}")
        conn.rollback()
    cur.close()
    conn.close()

# ── Habit Library ──────────────────────────────────────────────────────────────
HABIT_LIBRARY = [
    # ── Wellness ──────────────────────────────────────────────────────────────
    {"name": "Drink Water 💧",          "description": "Drink 8 glasses of water",             "color": "#5b8fa8", "icon": "💧", "category": "Wellness"},
    {"name": "Take Vitamins 🌸",        "description": "Daily supplements",                    "color": "#e8a598", "icon": "🌸", "category": "Wellness"},
    {"name": "Limit Caffeine ☕",       "description": "Max 1 coffee or tea",                  "color": "#c4a882", "icon": "☕", "category": "Wellness"},
    {"name": "Morning Sunlight ☀️",    "description": "Get sunlight within an hour of waking", "color": "#f0d080", "icon": "☀️", "category": "Wellness"},
    {"name": "Cold Shower 🚿",          "description": "End your shower with 30s of cold water","color": "#90c4d8", "icon": "🚿", "category": "Wellness"},
    {"name": "Skincare Routine 🧴",     "description": "Morning or evening skincare",          "color": "#f0c8b8", "icon": "🧴", "category": "Wellness"},
    {"name": "Wash Face 🫧",            "description": "Cleanse morning and night",             "color": "#c8e8f0", "icon": "🫧", "category": "Wellness"},
    # ── Movement ──────────────────────────────────────────────────────────────
    {"name": "Move Your Body 🌿",       "description": "30 min of gentle movement",            "color": "#86b49c", "icon": "🌿", "category": "Movement"},
    {"name": "Stretch 🧘",              "description": "10 min of stretching",                 "color": "#b8a9c9", "icon": "🧘", "category": "Movement"},
    {"name": "Go Outside 🌤️",          "description": "Get fresh air for 15 min",             "color": "#a8c8a0", "icon": "🌤️", "category": "Movement"},
    {"name": "Walk 6,000 Steps 👟",     "description": "Aim for a gentle daily step goal",     "color": "#a0c4a8", "icon": "👟", "category": "Movement"},
    {"name": "Yoga Flow 🌸",            "description": "A short yoga sequence",                "color": "#c8b4d8", "icon": "🌸", "category": "Movement"},
    {"name": "Dance It Out 💃",         "description": "Put on a song and move freely",        "color": "#f0b8d0", "icon": "💃", "category": "Movement"},
    # ── Mind ──────────────────────────────────────────────────────────────────
    {"name": "Meditate 🌙",             "description": "5-10 min of mindfulness",              "color": "#9ab0c4", "icon": "🌙", "category": "Mind"},
    {"name": "Journal ✍️",              "description": "Write down your thoughts",             "color": "#f2c4a0", "icon": "✍️", "category": "Mind"},
    {"name": "Read 📖",                 "description": "Read for 20 minutes",                  "color": "#c4b0a0", "icon": "📖", "category": "Mind"},
    {"name": "Gratitude Practice 🙏",   "description": "Write 3 things you're grateful for",   "color": "#f0d8a8", "icon": "🙏", "category": "Mind"},
    {"name": "Digital Detox 🌿",        "description": "One hour with no phone or screens",    "color": "#a8c4a0", "icon": "🌿", "category": "Mind"},
    {"name": "Learn Something New 🎓",  "description": "Watch, read, or listen to learn",      "color": "#b8c8e8", "icon": "🎓", "category": "Mind"},
    # ── Rest ──────────────────────────────────────────────────────────────────
    {"name": "Sleep by 10pm 😴",        "description": "Wind down and sleep early",            "color": "#a0b4c8", "icon": "😴", "category": "Rest"},
    {"name": "Limit Screen Time 📵",    "description": "No screens 1hr before bed",            "color": "#b0a8c8", "icon": "📵", "category": "Rest"},
    {"name": "Afternoon Rest 🛋️",      "description": "10-20 min rest or nap",                "color": "#c8b8d8", "icon": "🛋️", "category": "Rest"},
    {"name": "Wind-Down Routine 🕯️",   "description": "A calming ritual before bed",          "color": "#d8c4b0", "icon": "🕯️", "category": "Rest"},
    {"name": "Sleep 8 Hours 💤",        "description": "Prioritise a full night of sleep",     "color": "#9098c0", "icon": "💤", "category": "Rest"},
    # ── Nutrition ─────────────────────────────────────────────────────────────
    {"name": "Eat a Warm Meal 🍲",      "description": "Nourish yourself with a warm meal",    "color": "#e8b87a", "icon": "🍲", "category": "Nutrition"},
    {"name": "Eat Iron-Rich Foods 🥗",  "description": "Spinach, lentils, or fortified foods", "color": "#a8c890", "icon": "🥗", "category": "Nutrition"},
    {"name": "Eat More Vegetables 🥦",  "description": "Add veggies to at least one meal",     "color": "#88b878", "icon": "🥦", "category": "Nutrition"},
    {"name": "Eat Breakfast 🌅",        "description": "Start the day with a nourishing meal", "color": "#f8d090", "icon": "🌅", "category": "Nutrition"},
    {"name": "Reduce Sugar 🍬",         "description": "Skip added sugar today",               "color": "#f0a8b8", "icon": "🍬", "category": "Nutrition"},
    {"name": "Omega-3 Foods 🐟",        "description": "Salmon, walnuts, or flaxseed",         "color": "#88b8d0", "icon": "🐟", "category": "Nutrition"},
    # ── Social ────────────────────────────────────────────────────────────────
    {"name": "Connect with Someone 💌", "description": "Reach out to a friend or family",      "color": "#f0b8c0", "icon": "💌", "category": "Social"},
    {"name": "Acts of Kindness 🤝",     "description": "Do something kind for someone",        "color": "#f8c8a8", "icon": "🤝", "category": "Social"},
    {"name": "Quality Time 🫶",         "description": "Be fully present with someone you love","color": "#f0b0c8", "icon": "🫶", "category": "Social"},
    {"name": "Set a Boundary 🌸",       "description": "Honour your needs in a relationship",  "color": "#d8b0c8", "icon": "🌸", "category": "Social"},
    # ── Cycle ─────────────────────────────────────────────────────────────────
    {"name": "Track Symptoms 🩺",       "description": "Log any cycle-related symptoms",       "color": "#e8a0b0", "icon": "🩺", "category": "Cycle"},
    {"name": "Heat Therapy 🌡️",        "description": "Use a heat pad for cramp relief",      "color": "#f4c4a8", "icon": "🌡️", "category": "Cycle"},
    {"name": "Rest on Heavy Days 🛏️",  "description": "Give yourself permission to slow down", "color": "#c8a8c0", "icon": "🛏️", "category": "Cycle"},
    {"name": "Magnesium Supplement 💊", "description": "May help with cramps and mood",        "color": "#b8c8e0", "icon": "💊", "category": "Cycle"},
    {"name": "Gentle Walk 🌸",          "description": "Light movement to ease discomfort",    "color": "#c8e0c0", "icon": "🌸", "category": "Cycle"},
    # ── Sustainability 🌍 ─────────────────────────────────────────────────────
    {"name": "Use a Reusable Bottle ♻️","description": "Ditch single-use plastic today",       "color": "#7ab89a", "icon": "♻️", "category": "Sustainability"},
    {"name": "Meatless Meal 🌱",        "description": "Eat one plant-based meal today",        "color": "#98c888", "icon": "🌱", "category": "Sustainability"},
    {"name": "Bring a Tote Bag 👜",     "description": "Skip the plastic bag",                 "color": "#c8b888", "icon": "👜", "category": "Sustainability"},
    {"name": "Shorter Shower 🚿",       "description": "Keep it under 5 minutes",              "color": "#88c0c8", "icon": "🚿", "category": "Sustainability"},
    {"name": "Turn Off Lights 💡",      "description": "Switch off lights when leaving a room", "color": "#f0d870", "icon": "💡", "category": "Sustainability"},
    {"name": "Walk or Cycle 🚲",        "description": "Choose legs over a car today",         "color": "#a0c8a0", "icon": "🚲", "category": "Sustainability"},
    {"name": "Buy Nothing New 🛍️",     "description": "Go a day without purchasing anything",  "color": "#c8b0a0", "icon": "🛍️", "category": "Sustainability"},
    {"name": "Compost Scraps 🌿",       "description": "Compost food scraps instead of binning","color": "#a8bc80", "icon": "🌿", "category": "Sustainability"},
]

# ── Auth helpers ───────────────────────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' not in session:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

# ── Garden helpers ─────────────────────────────────────────────────────────────
def calculate_garden_score(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM periods WHERE user_id=%s", (user_id,))
    periods_count = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM habit_logs WHERE user_id=%s AND completed=TRUE", (user_id,))
    habit_count = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM checkins WHERE user_id=%s", (user_id,))
    checkin_count = cur.fetchone()['cnt']
    cur.close()
    conn.close()
    return int(periods_count * 10 + habit_count * 2 + checkin_count * 3)

def update_garden(user_id):
    score = calculate_garden_score(user_id)
    conn = get_db()
    cur = conn.cursor()

    plant_thresholds = [
        (0,   'seedling',    1, 20, 55),
        (10,  'daisy',       1, 35, 70),
        (25,  'rose',        1, 60, 65),
        (50,  'sunflower',   1, 75, 50),
        (100, 'lavender',    1, 45, 40),
        (150, 'cherry_blossom', 1, 25, 35),
        (200, 'lotus',       1, 65, 30),
    ]

    for threshold, plant_type, stage, px, py in plant_thresholds:
        if score >= threshold:
            cur.execute("""
                INSERT INTO garden_items (user_id, plant_type, growth_stage, position_x, position_y)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, plant_type, stage, px, py))

    # Update growth stages based on score
    stage = min(5, max(1, score // 20 + 1))
    cur.execute("""
        UPDATE garden_items SET growth_stage = LEAST(5, %s)
        WHERE user_id = %s
    """, (stage, user_id))

    conn.commit()
    cur.close()
    conn.close()

def predict_next_period(user):
    if not user or not user['last_period_date']:
        return None, None
    last = user['last_period_date']
    cycle = user['cycle_length'] or 28
    period_len = user['period_length'] or 5
    next_start = last + timedelta(days=cycle)
    next_end = next_start + timedelta(days=period_len - 1)
    return next_start, next_end

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ── AUTH ───────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=%s OR username=%s",
            (identifier, identifier)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        error = "Invalid credentials. Please try again."
    return render_template('auth/login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    errors = {}
    form_data = {}
    if request.method == 'POST':
        form_data = request.form.to_dict()
        username = form_data.get('username', '').strip()
        email = form_data.get('email', '').strip()
        password = form_data.get('password', '')
        confirm = form_data.get('confirm_password', '')
        first_name = form_data.get('first_name', '').strip()
        last_name = form_data.get('last_name', '').strip()
        birth_date = form_data.get('birth_date') or None
        cycle_length = int(form_data.get('cycle_length', 28))
        period_length = int(form_data.get('period_length', 5))
        last_period_date = form_data.get('last_period_date') or None
        contraceptive = form_data.get('contraceptive_method', '').strip() or None
        ttc = form_data.get('trying_to_conceive') == 'on'
        symptoms_raw = form_data.get('typical_symptoms', '')
        symptoms = [s.strip() for s in symptoms_raw.split(',') if s.strip()] if symptoms_raw else []

        if not username or len(username) < 3:
            errors['username'] = 'Username must be at least 3 characters.'
        if not email or '@' not in email:
            errors['email'] = 'Please enter a valid email.'
        if len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters.'
        if password != confirm:
            errors['confirm_password'] = 'Passwords do not match.'

        if not errors:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username=%s OR email=%s", (username, email))
            existing = cur.fetchone()
            if existing:
                errors['username'] = 'Username or email already exists.'
            else:
                pw_hash = generate_password_hash(password)
                cur.execute("""
                    INSERT INTO users
                    (username, email, password_hash, first_name, last_name, birth_date,
                     cycle_length, period_length, last_period_date, typical_symptoms,
                     contraceptive_method, trying_to_conceive)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (username, email, pw_hash, first_name, last_name, birth_date,
                      cycle_length, period_length, last_period_date,
                      symptoms if symptoms else None,
                      contraceptive, ttc))
                new_user = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()

                # Seed initial garden item
                session['user_id'] = new_user['id']
                session['username'] = username
                conn2 = get_db()
                cur2 = conn2.cursor()
                cur2.execute("""
                    INSERT INTO garden_items (user_id, plant_type, growth_stage, position_x, position_y)
                    VALUES (%s, 'seedling', 1, 20, 55)
                """, (new_user['id'],))
                # Seed default habits
                default_habits = [
                    ('Drink Water 💧', 'Drink 8 glasses of water', '#5b8fa8'),
                    ('Move Your Body 🌿', '30 min of movement', '#86b49c'),
                    ('Take Vitamins 🌸', 'Daily supplements', '#e8a598'),
                ]
                for name, desc, color in default_habits:
                    cur2.execute("""
                        INSERT INTO habits (user_id, name, description, color)
                        VALUES (%s, %s, %s, %s)
                    """, (new_user['id'], name, desc, color))
                conn2.commit()
                cur2.close()
                conn2.close()

                flash('Welcome to Bloom! 🌸 Your garden is ready.', 'success')
                return redirect(url_for('dashboard'))
            cur.close()
            conn.close()

    return render_template('auth/register.html', errors=errors, form_data=form_data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── DASHBOARD ──────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    conn = get_db()
    cur = conn.cursor()

    # Today's checkin
    cur.execute("SELECT * FROM checkins WHERE user_id=%s AND checkin_date=%s",
                (user['id'], date.today()))
    today_checkin = cur.fetchone()

    # Recent habits
    cur.execute("SELECT * FROM habits WHERE user_id=%s AND active=TRUE", (user['id'],))
    habits = cur.fetchall()

    habit_status = {}
    for h in habits:
        cur.execute("""
            SELECT completed FROM habit_logs
            WHERE habit_id=%s AND log_date=%s
        """, (h['id'], date.today()))
        log = cur.fetchone()
        habit_status[h['id']] = log['completed'] if log else False

    # Garden items
    cur.execute("SELECT * FROM garden_items WHERE user_id=%s ORDER BY earned_at", (user['id'],))
    garden = cur.fetchall()

    # Stats
    score = calculate_garden_score(user['id'])
    cur.execute("SELECT COUNT(*) as cnt FROM periods WHERE user_id=%s", (user['id'],))
    period_count = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM checkins WHERE user_id=%s", (user['id'],))
    checkin_count = cur.fetchone()['cnt']
    cur.execute("""
        SELECT COUNT(*) as cnt FROM habit_logs
        WHERE user_id=%s AND log_date >= %s AND completed=TRUE
    """, (user['id'], date.today() - timedelta(days=7)))
    weekly_habits = cur.fetchone()['cnt']

    # Streak calculation
    streak = 0
    check_date = date.today()
    while True:
        cur.execute("SELECT id FROM checkins WHERE user_id=%s AND checkin_date=%s",
                    (user['id'], check_date))
        if cur.fetchone():
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Period prediction
    next_start, next_end = predict_next_period(user)
    days_until = (next_start - date.today()).days if next_start else None

    cur.close()
    conn.close()

    update_garden(user['id'])

    return render_template('dashboard.html',
        user=user,
        current_hour=datetime.now().hour,
        today_checkin=today_checkin,
        habits=habits,
        habit_status=habit_status,
        garden=garden,
        score=score,
        period_count=period_count,
        checkin_count=checkin_count,
        weekly_habits=weekly_habits,
        streak=streak,
        next_period_start=next_start,
        next_period_end=next_end,
        days_until_period=days_until,
        today=date.today()
    )

# ── GARDEN ────────────────────────────────────────────────────────────────────

@app.route('/garden')
@login_required
def garden():
    user = get_current_user()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM garden_items WHERE user_id=%s ORDER BY earned_at", (user['id'],))
    garden_items = cur.fetchall()
    score = calculate_garden_score(user['id'])
    cur.execute("SELECT COUNT(*) as cnt FROM periods WHERE user_id=%s", (user['id'],))
    period_count = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM checkins WHERE user_id=%s", (user['id'],))
    checkin_count = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM habit_logs WHERE user_id=%s AND completed=TRUE", (user['id'],))
    habit_count = cur.fetchone()['cnt']
    cur.close()
    conn.close()
    next_milestone = ((score // 25) + 1) * 25
    return render_template('garden.html',
        user=user,
        garden_items=garden_items,
        score=score,
        period_count=period_count,
        checkin_count=checkin_count,
        habit_count=habit_count,
        next_milestone=next_milestone
    )

# ── CALENDAR ──────────────────────────────────────────────────────────────────

@app.route('/calendar')
@login_required
def calendar_view():
    user = get_current_user()
    view = request.args.get('view', 'month')
    year = int(request.args.get('year', date.today().year))
    month = int(request.args.get('month', date.today().month))
    day = int(request.args.get('day', date.today().day))

    conn = get_db()
    cur = conn.cursor()

    # All periods
    cur.execute("SELECT * FROM periods WHERE user_id=%s ORDER BY start_date", (user['id'],))
    periods = cur.fetchall()

    # All checkins for the month
    cur.execute("""
        SELECT * FROM checkins WHERE user_id=%s
        AND EXTRACT(YEAR FROM checkin_date)=%s
        AND EXTRACT(MONTH FROM checkin_date)=%s
    """, (user['id'], year, month))
    checkins = cur.fetchall()

    # Habit logs for the month
    cur.execute("""
        SELECT hl.*, h.name, h.color, h.icon FROM habit_logs hl
        JOIN habits h ON hl.habit_id = h.id
        WHERE hl.user_id=%s
        AND EXTRACT(YEAR FROM log_date)=%s
        AND EXTRACT(MONTH FROM log_date)=%s
    """, (user['id'], year, month))
    habit_logs = cur.fetchall()

    cur.close()
    conn.close()

    # Predict future periods
    predicted_periods = []
    next_start, next_end = predict_next_period(user)
    if next_start:
        for i in range(6):
            ps = next_start + timedelta(days=(user['cycle_length'] or 28) * i)
            pe = next_end + timedelta(days=(user['cycle_length'] or 28) * i)
            predicted_periods.append({'start': ps, 'end': pe})

    # Serialize for JSON
    periods_json = [
        {'id': p['id'], 'start': str(p['start_date']),
         'end': str(p['end_date']) if p['end_date'] else str(p['start_date']),
         'flow': p['flow_intensity'], 'notes': p['notes'], 'actual': True}
        for p in periods
    ]
    for pp in predicted_periods:
        periods_json.append({'start': str(pp['start']), 'end': str(pp['end']), 'actual': False})

    checkins_json = [
        {'date': str(c['checkin_date']), 'mood': c['mood'], 'energy': c['energy'],
         'pain': c['pain_level'], 'symptoms': c['symptoms'], 'notes': c['notes']}
        for c in checkins
    ]

    habit_logs_json = [
        {'date': str(hl['log_date']), 'habit': hl['name'],
         'color': hl['color'], 'completed': hl['completed']}
        for hl in habit_logs
    ]

    import calendar as cal_module
    return render_template('calendar.html',
        user=user,
        view=view,
        year=year,
        month=month,
        day=day,
        month_name=cal_module.month_name[month],
        periods_json=json.dumps(periods_json),
        checkins_json=json.dumps(checkins_json),
        habit_logs_json=json.dumps(habit_logs_json),
        today=date.today()
    )

# ── CHECK-IN ──────────────────────────────────────────────────────────────────

@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    user = get_current_user()
    checkin_date = request.args.get('date', str(date.today()))
    conn = get_db()
    cur = conn.cursor()

    # existing checkin
    cur.execute("SELECT * FROM checkins WHERE user_id=%s AND checkin_date=%s",
                (user['id'], checkin_date))
    existing = cur.fetchone()

    if request.method == 'POST':
        mood = int(request.form.get('mood', 3))
        energy = int(request.form.get('energy', 3))
        pain = int(request.form.get('pain_level', 0))
        notes = request.form.get('notes', '').strip()
        symptoms_raw = request.form.getlist('symptoms')

        if existing:
            cur.execute("""
                UPDATE checkins SET mood=%s, energy=%s, pain_level=%s, symptoms=%s, notes=%s
                WHERE user_id=%s AND checkin_date=%s
            """, (mood, energy, pain, symptoms_raw or None, notes, user['id'], checkin_date))
        else:
            cur.execute("""
                INSERT INTO checkins (user_id, checkin_date, mood, energy, pain_level, symptoms, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user['id'], checkin_date, mood, energy, pain,
                  symptoms_raw if symptoms_raw else None, notes))
        conn.commit()
        cur.close()
        conn.close()
        update_garden(user['id'])
        flash('Check-in saved! Your garden is blooming. 🌸', 'success')
        return redirect(url_for('dashboard'))

    # Recent checkins for context
    cur.execute("""
        SELECT * FROM checkins WHERE user_id=%s
        ORDER BY checkin_date DESC LIMIT 7
    """, (user['id'],))
    recent = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('checkin.html',
        user=user,
        existing=existing,
        checkin_date=checkin_date,
        recent_checkins=recent
    )

# ── HABITS ────────────────────────────────────────────────────────────────────

@app.route('/habits')
@login_required
def habits():
    user = get_current_user()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM habits WHERE user_id=%s AND active=TRUE ORDER BY created_at", (user['id'],))
    habits_list = cur.fetchall()

    today_logs = {}
    week_stats = {}
    for h in habits_list:
        cur.execute("SELECT completed FROM habit_logs WHERE habit_id=%s AND log_date=%s",
                    (h['id'], date.today()))
        log = cur.fetchone()
        today_logs[h['id']] = log['completed'] if log else False

        cur.execute("""
            SELECT COUNT(*) as cnt FROM habit_logs
            WHERE habit_id=%s AND log_date >= %s AND completed=TRUE
        """, (h['id'], date.today() - timedelta(days=6)))
        week_stats[h['id']] = cur.fetchone()['cnt']

    cur.close()
    conn.close()
    return render_template('habits.html',
        user=user,
        habits=habits_list,
        habit_status=today_logs,
        week_stats=week_stats,
        today=date.today()
    )

@app.route('/habits/toggle', methods=['POST'])
@login_required
def toggle_habit():
    data = request.get_json()
    habit_id = data.get('habit_id')
    log_date = data.get('date', str(date.today()))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM habits WHERE id=%s AND user_id=%s",
                (habit_id, session['user_id']))
    if not cur.fetchone():
        cur.close(); conn.close()
        return jsonify({'error': 'unauthorized'}), 403

    cur.execute("SELECT id, completed FROM habit_logs WHERE habit_id=%s AND log_date=%s",
                (habit_id, log_date))
    existing = cur.fetchone()
    if existing:
        new_state = not existing['completed']
        cur.execute("UPDATE habit_logs SET completed=%s WHERE id=%s", (new_state, existing['id']))
    else:
        new_state = True
        cur.execute("INSERT INTO habit_logs (habit_id, user_id, log_date, completed) VALUES (%s,%s,%s,%s)",
                    (habit_id, session['user_id'], log_date, True))
    conn.commit()
    cur.close(); conn.close()
    update_garden(session['user_id'])
    return jsonify({'completed': new_state})

@app.route('/habits/add', methods=['POST'])
@login_required
def add_habit():
    name = request.form.get('name', '').strip()
    desc = request.form.get('description', '').strip()
    color = request.form.get('color', '#86b49c')
    icon = request.form.get('icon', '✿')
    if name:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO habits (user_id, name, description, color, icon)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], name, desc, color, icon))
        conn.commit()
        cur.close(); conn.close()
        flash('Habit added! 🌱', 'success')
    return redirect(url_for('habits'))

@app.route('/habits/delete/<int:habit_id>', methods=['POST'])
@login_required
def delete_habit(habit_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE habits SET active=FALSE WHERE id=%s AND user_id=%s",
                (habit_id, session['user_id']))
    conn.commit()
    cur.close(); conn.close()
    flash('Habit removed.', 'info')
    return redirect(url_for('habits'))


@app.route('/habits/pause/<int:habit_id>', methods=['POST'])
@login_required
def pause_habit(habit_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT paused FROM habits WHERE id=%s AND user_id=%s AND active=TRUE",
                (habit_id, session['user_id']))
    habit = cur.fetchone()
    if habit:
        new_state = not habit['paused']
        cur.execute("UPDATE habits SET paused=%s WHERE id=%s AND user_id=%s",
                    (new_state, habit_id, session['user_id']))
        conn.commit()
        msg = 'Habit paused. No streaks affected. 🌿' if new_state else 'Habit resumed! 🌱'
        flash(msg, 'info')
    cur.close(); conn.close()
    return redirect(url_for('habits'))

@app.route('/habits/library')
@login_required
def habit_library():
    user = get_current_user()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM habits WHERE user_id=%s AND active=TRUE", (session['user_id'],))
    existing_names = {row['name'] for row in cur.fetchall()}
    cur.close(); conn.close()
    return render_template('habit_library.html',
        user=user,
        library=HABIT_LIBRARY,
        existing_names=existing_names
    )

@app.route('/habits/library/add', methods=['POST'])
@login_required
def add_from_library():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    color = request.form.get('color', '#86b49c')
    icon = request.form.get('icon', '✿')
    if name:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM habits WHERE user_id=%s AND name=%s AND active=TRUE",
                    (session['user_id'], name))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO habits (user_id, name, description, color, icon)
                VALUES (%s, %s, %s, %s, %s)
            """, (session['user_id'], name, description, color, icon))
            conn.commit()
            flash(f'{name} added to your habits! 🌱', 'success')
        else:
            flash('You already have this habit.', 'info')
        cur.close(); conn.close()
    return redirect(url_for('habit_library'))

# ── PERIOD TRACKING ───────────────────────────────────────────────────────────

@app.route('/period/log', methods=['POST'])
@login_required
def log_period():
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    flow = data.get('flow_intensity', 'medium')
    notes = data.get('notes', '')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO periods (user_id, start_date, end_date, flow_intensity, notes)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING RETURNING id
    """, (session['user_id'], start_date, end_date, flow, notes))
    new_period = cur.fetchone()
    # Update last_period_date
    cur.execute("UPDATE users SET last_period_date=%s WHERE id=%s",
                (start_date, session['user_id']))
    conn.commit()
    cur.close(); conn.close()
    update_garden(session['user_id'])
    return jsonify({'success': True, 'id': new_period['id'] if new_period else None})

@app.route('/period/delete/<int:period_id>', methods=['POST'])
@login_required
def delete_period(period_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM periods WHERE id=%s AND user_id=%s",
                (period_id, session['user_id']))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({'success': True})

@app.route('/period/edit/<int:period_id>', methods=['POST'])
@login_required
def edit_period(period_id):
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date') or None
    flow = data.get('flow_intensity', 'medium')
    notes = data.get('notes', '')
    if not start_date:
        return jsonify({'success': False, 'error': 'start_date required'}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM periods WHERE id=%s AND user_id=%s",
                (period_id, session['user_id']))
    if not cur.fetchone():
        cur.close(); conn.close()
        return jsonify({'success': False, 'error': 'not found'}), 404
    cur.execute("""
        UPDATE periods SET start_date=%s, end_date=%s, flow_intensity=%s, notes=%s
        WHERE id=%s AND user_id=%s
    """, (start_date, end_date, flow, notes, period_id, session['user_id']))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({'success': True})

# ── API: Garden data ──────────────────────────────────────────────────────────

@app.route('/api/garden')
@login_required
def api_garden():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM garden_items WHERE user_id=%s", (session['user_id'],))
    items = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([dict(i) for i in items])

@app.route('/api/stats')
@login_required
def api_stats():
    user = get_current_user()
    score = calculate_garden_score(user['id'])
    return jsonify({'score': score})

# ── Settings ──────────────────────────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_current_user()
    errors = {}
    if request.method == 'POST':
        cycle_length = int(request.form.get('cycle_length', 28))
        period_length = int(request.form.get('period_length', 5))
        last_period_date = request.form.get('last_period_date') or None
        contraceptive = request.form.get('contraceptive_method', '').strip() or None
        ttc = request.form.get('trying_to_conceive') == 'on'
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        symptoms_raw = request.form.get('typical_symptoms', '')
        symptoms = [s.strip() for s in symptoms_raw.split(',') if s.strip()] if symptoms_raw else []

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users SET cycle_length=%s, period_length=%s, last_period_date=%s,
            contraceptive_method=%s, trying_to_conceive=%s, first_name=%s, last_name=%s,
            typical_symptoms=%s WHERE id=%s
        """, (cycle_length, period_length, last_period_date, contraceptive, ttc,
              first_name, last_name, symptoms if symptoms else None, user['id']))
        conn.commit()
        cur.close(); conn.close()
        flash('Settings updated! 🌿', 'success')
        return redirect(url_for('settings'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM periods WHERE user_id=%s ORDER BY start_date DESC LIMIT 10", (user['id'],))
    recent_periods = cur.fetchall()
    cur.close(); conn.close()

    return render_template('settings.html', user=user, recent_periods=recent_periods)
# ── Suggestions ─────────────────────────────────────────────────────────────────
@app.route('/api/suggestions')
@login_required
def api_suggestions():
    user_id = session['user_id']
    suggestion = generate_suggestion_for_user(user_id)
    return jsonify(suggestion)


def generate_suggestion_for_user(user_id):
    conn = get_db()
    cur = conn.cursor()

    # Recent checkins (last 7 days)
    cur.execute("""
        SELECT mood, energy, pain_level, symptoms, notes, checkin_date
        FROM checkins
        WHERE user_id=%s
        ORDER BY checkin_date DESC
        LIMIT 7
    """, (user_id,))
    checkins = cur.fetchall()

    # Recent habit logs (last 7 days)
    cur.execute("""
        SELECT completed
        FROM habit_logs
        WHERE user_id=%s AND log_date >= %s
    """, (user_id, date.today() - timedelta(days=7)))
    habit_logs = cur.fetchall()

    # User info (cycle, last period)
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    # Build suggestion object
    suggestion = {
        "title": "Recommendation",
        "message": "",
        "category": "",
        "dismissible": True,
        "actions": ["accept", "modify", "ignore"]
    }

    # --- Habit pattern suggestion ---
    if habit_logs:
        completion_rate = sum(1 for h in habit_logs if h['completed']) / len(habit_logs)
        if completion_rate < 0.4:
            suggestion["category"] = "Habits"
            suggestion["message"] = (
                "It looks like the past week has been full. "
                "If you'd like, you could focus on just one small habit today. "
                "Gentle consistency can support your overall well‑being."
            )
            return suggestion

    # --- Emotional check‑in suggestion ---
    if checkins:
        last = checkins[0]
        if last['mood'] <= 2:
            suggestion["category"] = "Emotional Well‑Being"
            suggestion["message"] = (
                "Your recent check‑ins show some lower moods. "
                "A grounding activity or a few minutes of rest might help, "
                "if that feels right for you."
            )
            return suggestion

        if last['energy'] <= 2:
            suggestion["category"] = "Energy"
            suggestion["message"] = (
                "You've noted lower energy recently. "
                "A gentle, restorative activity could support you today."
            )
            return suggestion

        if last['pain_level'] >= 6:
            suggestion["category"] = "Comfort"
            suggestion["message"] = (
                "You've logged higher discomfort. "
                "If you'd like, you could try a warm compress or light stretching. "
                "Only if it feels supportive."
            )
            return suggestion

    # --- Cycle-based suggestion ---
    next_start, _ = predict_next_period(user)
    if next_start:
        days_until = (next_start - date.today()).days
        if 0 <= days_until <= 3:
            suggestion["category"] = "Cycle Awareness"
            suggestion["message"] = (
                "Your next period may be approaching soon. "
                "You might consider preparing comfort items or planning a lighter day, "
                "if that feels helpful."
            )
            return suggestion

    # --- Default suggestion ---
    suggestion["category"] = "General Wellness"
    suggestion["message"] = (
        "You're doing a wonderful job staying connected with your habits and cycle. "
        "If you'd like, you can explore a new gentle wellness activity this week."
    )

    return suggestion

# ── Emotional Patterns ─────────────────────────────────────────────────────────────────
@app.route('/api/emotional-patterns')
@login_required
def emotional_patterns():
    user_id = session['user_id']
    insight = generate_emotional_pattern(user_id)
    return jsonify(insight)
def generate_emotional_pattern(user_id):
    conn = get_db()
    cur = conn.cursor()

    # Get last 30 days of checkins
    cur.execute("""
        SELECT mood, energy, pain_level, checkin_date
        FROM checkins
        WHERE user_id=%s AND checkin_date >= %s
        ORDER BY checkin_date DESC
    """, (user_id, date.today() - timedelta(days=30)))
    rows = cur.fetchall()

    cur.close(); conn.close()

    if len(rows) < 5:
        return {
            "title": "Emotional Pattern",
            "message": "As you continue checking in, Bloom will help you notice gentle emotional patterns over time."
        }

    # Average mood by week
    moods = [r['mood'] for r in rows]
    avg_mood = sum(moods) / len(moods)

    # Simple insight examples
    if avg_mood <= 2.5:
        return {
            "title": "Emotional Pattern",
            "message": "Your recent check‑ins show a trend toward lower moods. You might consider adding a grounding or comforting activity this week."
        }

    if avg_mood >= 4:
        return {
            "title": "Emotional Pattern",
            "message": "You've logged brighter moods recently. This could be a lovely time to nurture creativity or connection."
        }

    return {
        "title": "Emotional Pattern",
        "message": "Your emotional patterns this month show a gentle balance. Staying aware of your feelings can help you stay grounded."
    }
@app.route('/api/save-insight', methods=['POST'])
@login_required
def save_insight():
    user_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO emotional_insights (user_id, saved_at) VALUES (%s, NOW())", (user_id,))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"status": "saved"})

@app.route('/emotional-patterns')
@login_required
def emotional_patterns_page():
    user_id = session['user_id']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT mood, energy, pain_level, checkin_date
        FROM checkins
        WHERE user_id=%s AND checkin_date >= %s
        ORDER BY checkin_date ASC
    """, (user_id, date.today() - timedelta(days=90)))

    rows = cur.fetchall()
    cur.close();
    conn.close()

    # FIXED: use dict keys instead of tuple indexes
    data = [
        {
            "mood": r["mood"],
            "energy": r["energy"],
            "pain": r["pain_level"],
            "date": r["checkin_date"]
        }
        for r in rows
    ]

    # ------------------------------
    # 1. WEEKLY EMOTIONAL RHYTHM
    # ------------------------------
    weekly = {i: [] for i in range(7)}  # 0=Mon
    for entry in data:
        weekday = entry["date"].weekday()
        weekly[weekday].append(entry["mood"])

    weekly_avg = [
        round(sum(vals)/len(vals), 2) if vals else None
        for vals in weekly.values()
    ]

    # ------------------------------
    # 2. MOOD–ENERGY CORRELATION
    # ------------------------------
    moods = [d["mood"] for d in data]
    energies = [d["energy"] for d in data]

    if len(moods) > 1:
        import numpy as np
        correlation = float(np.corrcoef(moods, energies)[0][1])
    else:
        correlation = None

    # ------------------------------
    # 3. PERIOD‑RELATED EMOTIONAL PATTERNS
    # ------------------------------
    # Pull period logs
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT start_date, end_date
        FROM periods
        WHERE user_id=%s
        ORDER BY start_date DESC
        LIMIT 3
    """, (user_id,))
    periods = cur.fetchall()
    cur.close(); conn.close()

    period_curve = {"-3": [], "-2": [], "-1": [], "0": [], "+1": [], "+2": [], "+3": []}

    for entry in data:
        for start, end in periods:
            delta = (entry["date"] - start).days
            if -3 <= delta <= 3:
                key = str(delta)
                period_curve[key].append(entry["mood"])

    period_avg = {
        k: (round(sum(v)/len(v), 2) if v else None)
        for k, v in period_curve.items()
    }

    # ------------------------------
    # 4. CYCLE PHASE EMOTIONS
    # ------------------------------
    # Simple phase classifier
    def get_phase(day):
        if 0 <= day <= 5:
            return "menstrual"
        if 6 <= day <= 13:
            return "follicular"
        if 14 <= day <= 16:
            return "ovulation"
        return "luteal"

    phase_map = {"menstrual": [], "follicular": [], "ovulation": [], "luteal": []}

    for entry in data:
        for start, end in periods:
            cycle_day = (entry["date"] - start).days
            if 0 <= cycle_day <= 28:
                phase = get_phase(cycle_day)
                phase_map[phase].append(entry["mood"])

    phase_avg = {
        phase: (round(sum(vals)/len(vals), 2) if vals else None)
        for phase, vals in phase_map.items()
    }

    return render_template(
        "emotional_patterns.html",
        weekly_avg=weekly_avg,
        correlation=correlation,
        period_avg=period_avg,
        phase_avg=phase_avg,
        data=data
    )

# ── Reflections ───────────────────────────────────────────────────────────────

@app.route('/reflect', methods=['GET', 'POST'])
@login_required
def reflect():
    user = get_current_user()
    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            cur.execute("""
                INSERT INTO reflections (user_id, entry_type, content) 
                VALUES (%s, 'free', %s)
            """, (user['id'], content))
            conn.commit()
            flash('Reflection saved. 🌿', 'success')
        cur.close()
        conn.close()
        return redirect(url_for('reflect'))

    cur.execute("""
        SELECT * FROM reflections
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 20
    """, (user['id'],))
    reflections = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('reflect.html', user=user, reflections=reflections, today=date.today())

@app.route('/reflect/edit/<int:reflection_id>', methods=['POST'])
@login_required
def edit_reflection(reflection_id):
    content = request.form.get('content', '').strip()
    if content:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE reflections SET content = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
        """, (content, reflection_id, session['user_id']))
        conn.commit()
        cur.close()
        conn.close()
        flash("Reflection updated. 🌿", 'success')
    return redirect(url_for('reflect'))

@app.route('/reflect/delete/<int:reflection_id>', methods=['POST'])
@login_required
def delete_reflection(reflection_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM reflections WHERE id = %s AND user_id = %s",
                    (reflection_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    flash('Refection deleted.', 'info')
    return redirect(url_for('reflect'))

@app.route('/api/notifications')
@login_required
def get_notifications():
    user = get_current_user()
    notifications = []
    today = date.today()

    conn = get_db()
    cur = conn.cursor()

    # 1. Check-in reminder — if no check-in today
    cur.execute("SELECT id FROM checkins WHERE user_id=%s AND checkin_date=%s",
                (user['id'], today))
    if not cur.fetchone():
        notifications.append({
            'id': 'checkin-today',
            'type': 'checkin',
            'title': 'Daily Check-in',
            'message': 'How are you feeling today? Take a moment to check in. 🌿',
            'link': '/checkin',
            'link_label': 'Check in now'
        })

    # 2. Upcoming period reminder — within 3 days
    next_start, _ = predict_next_period(user)
    if next_start:
        days_away = (next_start - today).days
        if 0 <= days_away <= 3:
            if days_away == 0:
                msg = 'Your period is predicted to start today. Take care of yourself. 🌹'
            elif days_away == 1:
                msg = 'Your period is predicted tomorrow. Be gentle with yourself. 🌹'
            else:
                msg = f'Your period is predicted in {days_away} days. A little heads-up. 🌹'
            notifications.append({
                'id': 'period-soon',
                'type': 'period',
                'title': 'Period Approaching',
                'message': msg,
                'link': '/calendar',
                'link_label': 'View Calendar'
            })

    # 3. Habit nudge — habits exist but none completed today
    cur.execute("SELECT id FROM habits WHERE user_id=%s AND active=TRUE", (user['id'],))
    habits = cur.fetchall()
    if habits:
        cur.execute("""
            SELECT COUNT(*) as cnt FROM habit_logs
            WHERE user_id=%s AND log_date=%s AND completed=TRUE
        """, (user['id'], today))
        completed = cur.fetchone()['cnt']
        if completed == 0:
            notifications.append({
                'id': 'habits-today',
                'type': 'habit',
                'title': 'Habits Today',
                'message': "You haven't logged any habits yet today. Small steps matter. ✨",
                'link': '/habits',
                'link_label': 'Log habits'
            })

    cur.close()
    conn.close()

    return jsonify({'notifications': notifications, 'count': len(notifications)})



# ── Run ───────────────────────────────────────────────────────────────────────

with app.app_context():
    try:
        init_db()
        migrate_db()
    except Exception as e:
        print(f"DB init warning: {e}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)