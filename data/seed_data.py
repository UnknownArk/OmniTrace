import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "media_analytics.db"
TRANSCRIPTS_DIR = DATA_DIR / "sample_transcripts"

def seed_sqlite_database():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE shows (
        show_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        genre TEXT NOT NULL,
        primary_language TEXT NOT NULL,
        total_seasons INTEGER NOT NULL,
        release_year INTEGER NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE episodes (
        episode_id INTEGER PRIMARY KEY,
        show_id INTEGER NOT NULL REFERENCES shows(show_id),
        season_num INTEGER NOT NULL,
        episode_num INTEGER NOT NULL,
        episode_title TEXT NOT NULL,
        duration_mins INTEGER NOT NULL,
        total_views INTEGER NOT NULL,
        completion_rate_pct REAL NOT NULL,
        avg_watch_duration_mins REAL NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE retention_dropoffs (
        event_id INTEGER PRIMARY KEY,
        episode_id INTEGER NOT NULL REFERENCES episodes(episode_id),
        timestamp_seconds INTEGER NOT NULL,
        timestamp_formatted TEXT NOT NULL,
        drop_off_pct REAL NOT NULL,
        exit_category TEXT NOT NULL,
        device_type TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE regional_performance (
        perf_id INTEGER PRIMARY KEY,
        show_id INTEGER NOT NULL REFERENCES shows(show_id),
        region TEXT NOT NULL,
        viewer_share_pct REAL NOT NULL,
        avg_rating REAL NOT NULL
    );
    """)

    cur.executemany("INSERT INTO shows VALUES (?, ?, ?, ?, ?, ?)", [
        (1, "Bhaichara", "Crime Drama", "Haryanvi/Hindi", 1, 2025),
        (2, "Dopamine Hustle", "Tech Drama", "Hinglish", 1, 2025),
        (3, "Chaudhar", "Political Thriller", "Haryanvi", 2, 2024),
    ])

    cur.executemany("INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        (101, 1, 1, 1, "The Oath", 28, 450000, 72.5, 21.2),
        (102, 1, 1, 2, "The Broken Deal", 26, 390000, 68.0, 18.5),
        (103, 1, 1, 3, "The Ambush", 24, 340000, 49.2, 13.1),
        (104, 1, 1, 4, "Crossroads", 27, 280000, 64.0, 17.8),
        (201, 2, 1, 1, "Burn Rate", 32, 220000, 52.0, 18.0),
        (202, 2, 1, 2, "Term Sheet", 30, 190000, 61.5, 19.4),
        (301, 3, 2, 1, "The Panchayat War", 35, 510000, 78.0, 28.1),
    ])

    cur.executemany("INSERT INTO retention_dropoffs VALUES (?, ?, ?, ?, ?, ?, ?)", [
        (1, 101, 180, "00:03:00", 6.2, "Intro Skip / Exit", "Mobile"),
        (2, 101, 600, "00:10:00", 4.1, "Normal Fatigue", "Mobile"),
        (3, 103, 790, "00:13:10", 38.4, "Abrupt Scene Exit", "Mobile"),
        (4, 103, 850, "00:14:10", 12.1, "Secondary Exit", "SmartTV"),
        (5, 201, 1125, "00:18:45", 41.2, "Pacing Lull", "Mobile"),
        (6, 301, 900, "00:15:00", 5.5, "Normal Exit", "SmartTV"),
    ])

    cur.executemany("INSERT INTO regional_performance VALUES (?, ?, ?, ?, ?)", [
        (1, 1, "Haryana", 54.0, 4.6),
        (2, 1, "Delhi-NCR", 26.0, 4.2),
        (3, 1, "Rajasthan", 14.0, 4.4),
        (4, 1, "UP-West", 6.0, 3.9),
        (5, 2, "Delhi-NCR", 68.0, 4.1),
        (6, 2, "Bangalore", 22.0, 4.5),
        (7, 3, "Haryana", 70.0, 4.8),
    ])

    conn.commit()
    conn.close()

def seed_transcripts():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    transcripts = [
        {
            "show_id": 1,
            "show_title": "Bhaichara",
            "episode_id": 101,
            "episode_num": 1,
            "scene_num": 1,
            "start_time": "00:00:30",
            "end_time": "00:03:00",
            "start_seconds": 30,
            "end_seconds": 180,
            "location": "Murthal Toll Plaza",
            "characters": ["Jaideep", "Virender"],
            "dialogue": (
                "Jaideep: Bhai, gaddi tezi se nikal. Peeche police ki patrolling team hai.\n"
                "Virender: Tension na le Jaideep, Rohtak bypass tak koi nahi rok sakega humein.\n"
                "Jaideep: Yeh consignment har haal mein sham tak pahunchana hai."
            ),
            "summary": "Opening scene: Jaideep and Virender evade toll check with cargo."
        },
        {
            "show_id": 1,
            "show_title": "Bhaichara",
            "episode_id": 103,
            "episode_num": 3,
            "scene_num": 2,
            "start_time": "00:07:00",
            "end_time": "00:09:30",
            "start_seconds": 420,
            "end_seconds": 570,
            "location": "Old Sugar Mill, Panipat",
            "characters": ["Jaideep", "Chaudhary Balwant"],
            "dialogue": (
                "Chaudhary: Tu samajhta hai tu is shahar ka naya raja ban gaya hai, Jaideep?\n"
                "Jaideep: Raja toh public banati hai, Chaudhary sahab. Hum toh bas faisle karte hain."
            ),
            "summary": "Confrontation between Jaideep and Chaudhary Balwant."
        },
        {
            "show_id": 1,
            "show_title": "Bhaichara",
            "episode_id": 103,
            "episode_num": 3,
            "scene_num": 4,
            "start_time": "00:12:40",
            "end_time": "00:14:45",
            "start_seconds": 760,
            "end_seconds": 885,
            "location": "Abandoned Warehouse Basement",
            "characters": ["Virender", "Mysterious Informant"],
            "dialogue": (
                "Virender: (whispering, slurred audio) The GPS beacon was planted under Jaideep's seat.\n"
                "Informant: (static and muffled) The signal is dead. You betrayed the wrong syndicate.\n"
                "[Audio cuts to jarring high-pitched static for 15 seconds. Unresolved narrative jump. "
                "Scene cuts abruptly into an unannounced black-and-white flashback without subtitle translations.]"
            ),
            "summary": "Audio defect and abrupt flashback transition in warehouse scene."
        },
        {
            "show_id": 1,
            "show_title": "Bhaichara",
            "episode_id": 108,
            "episode_num": 8,
            "scene_num": 5,
            "start_time": "00:15:00",
            "end_time": "00:18:00",
            "start_seconds": 900,
            "end_seconds": 1080,
            "location": "High Court Steps",
            "characters": ["Jaideep", "Advocate Mehra"],
            "dialogue": (
                "Advocate Mehra: If we present the ledger now, the entire district ministry falls.\n"
                "Jaideep: Present it tomorrow morning. Let the storm begin."
            ),
            "summary": "Dialogue from unreleased finale."
        }
    ]

    out_file = TRANSCRIPTS_DIR / "transcripts.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(transcripts, f, indent=2)

if __name__ == "__main__":
    seed_sqlite_database()
    seed_transcripts()
    print("Database and transcripts seeded successfully.")
