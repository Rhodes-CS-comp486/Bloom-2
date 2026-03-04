import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
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
    conn = get_db_connection()
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
        );
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
        );
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
        );
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
        );
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
        );
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
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized successfully.")

if __name__ == "__main__":
    init_db()
