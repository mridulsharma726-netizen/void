"""
VOID Academic Progress Tracker
==============================

Manages the SQLite database storing current subjects, completed chapters,
knowledge gaps, test history, and learning stats.
"""

import sqlite3
import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Resolve absolute path to database
ROOT_DIR = Path(__file__).parent.parent
DB_PATH = ROOT_DIR / "memory" / "academic_progress.db"

SUPPORTED_SUBJECTS = {
    "maths": "Mathematics",
    "business_stats": "Business Statistics",
    "applied_stats": "Applied Statistics",
    "critical_thinking": "Critical Thinking",
    "c_programming": "C Programming",
    "python": "Python Programming",
    "oop": "Object Oriented Programming",
    "dsa": "Data Structures & Algorithms",
    "dbms": "Database Systems",
    "adv_dbms": "Advanced Database Systems",
    "web_tech": "Web Technology",
    "os": "Operating Systems",
    "networks": "Computer Networks",
    "software_eng": "Software Engineering",
    "mobile_dev": "Mobile App Development",
    "ai_ml": "Artificial Intelligence & Machine Learning",
    "ethical_hacking": "Ethical Hacking",
    "indian_constitution": "Indian Constitution",
    "design_thinking": "Design Thinking",
    "analog_devices": "Analog Devices"
}

def get_connection():
    """Returns a SQLite connection to the academic progress DB, creating it if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Profile metadata (e.g. current_subject, current_chapter)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_profile (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # 2. Subjects registry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id TEXT PRIMARY KEY,
                subject_name TEXT UNIQUE,
                streak INTEGER DEFAULT 0,
                last_active TEXT,
                mastery_level TEXT DEFAULT 'Novice'
            )
        """)
        
        # 3. Researched Curriculum Structure
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS curriculum (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT,
                unit_title TEXT,
                chapter_title TEXT,
                subtopics_json TEXT,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
            )
        """)
        
        # 4. Completed topics/chapters tracker
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS completed_topics (
                subject_id TEXT,
                topic_id TEXT,
                completed_at TEXT,
                confidence INTEGER,
                PRIMARY KEY (subject_id, topic_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
            )
        """)
        
        # 5. Knowledge gaps / weak areas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_gaps (
                subject_id TEXT,
                topic_id TEXT,
                wrong_answers INTEGER DEFAULT 0,
                difficulty TEXT,
                last_reviewed TEXT,
                PRIMARY KEY (subject_id, topic_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
            )
        """)
        
        # 6. Legacy Viva / Quiz scoring history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS viva_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT,
                topic_id TEXT,
                score REAL,
                feedback TEXT,
                timestamp TEXT
            )
        """)
        
        # 7. Timed Test / Exam / Quiz History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT,
                topic_id TEXT,
                test_type TEXT,
                score REAL,
                correct_count INTEGER,
                wrong_count INTEGER,
                skipped_count INTEGER,
                time_taken INTEGER,
                feedback TEXT,
                timestamp TEXT,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
            )
        """)
        
        # 8. Flashcards Database Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT,
                topic_id TEXT,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                interval INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                next_review TEXT,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
            )
        """)
        
        # Migration: Ensure repetitions column exists
        try:
            cursor.execute("ALTER TABLE flashcards ADD COLUMN repetitions INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # 9. Analytics Log Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Populate subjects list
        for subj_id, subj_name in SUPPORTED_SUBJECTS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO subjects (subject_id, subject_name) VALUES (?, ?)",
                (subj_id, subj_name)
            )
            
        conn.commit()

# --- PROFILE SETTERS/GETTERS ---
def set_profile_value(key: str, value: str):
    """Sets a student profile configuration key."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO student_profile (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()

def get_profile_value(key: str, default: str = "") -> str:
    """Gets a student profile configuration key."""
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM student_profile WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

# --- PROGRESS UPDATES ---
def mark_topic_completed(subject_id: str, topic_id: str, confidence: int = 5):
    """Marks a topic as completed and reviews if it was in knowledge gaps."""
    init_db()
    completed_at = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO completed_topics (subject_id, topic_id, completed_at, confidence) VALUES (?, ?, ?, ?)",
            (subject_id, topic_id, completed_at, confidence)
        )
        if confidence >= 4:
            conn.execute(
                "DELETE FROM knowledge_gaps WHERE subject_id = ? AND topic_id = ?",
                (subject_id, topic_id)
            )
        conn.commit()
    update_streak(subject_id)

def record_knowledge_gap(subject_id: str, topic_id: str, difficulty: str = "Medium"):
    """Records a wrong answer/failure to master a topic, adding/updating knowledge gaps."""
    init_db()
    last_reviewed = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT wrong_answers FROM knowledge_gaps WHERE subject_id = ? AND topic_id = ?",
            (subject_id, topic_id)
        ).fetchone()
        
        if row:
            wrong_count = row["wrong_answers"] + 1
            conn.execute(
                "UPDATE knowledge_gaps SET wrong_answers = ?, last_reviewed = ?, difficulty = ? WHERE subject_id = ? AND topic_id = ?",
                (wrong_count, last_reviewed, difficulty, subject_id, topic_id)
            )
        else:
            conn.execute(
                "INSERT INTO knowledge_gaps (subject_id, topic_id, wrong_answers, difficulty, last_reviewed) VALUES (?, ?, 1, ?, ?)",
                (subject_id, topic_id, difficulty, last_reviewed)
            )
        conn.commit()

def record_viva_result(subject_id: str, topic_id: str, score: float, feedback: str):
    """Records the outcome of a Viva session."""
    init_db()
    timestamp = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO viva_history (subject_id, topic_id, score, feedback, timestamp) VALUES (?, ?, ?, ?, ?)",
            (subject_id, topic_id, score, feedback, timestamp)
        )
        
        # If score is low, record as a knowledge gap
        if score < 6.0:
            difficulty = "Medium" if score >= 4.0 else "High"
            row = conn.execute(
                "SELECT wrong_answers FROM knowledge_gaps WHERE subject_id = ? AND topic_id = ?",
                (subject_id, topic_id)
            ).fetchone()
            
            if row:
                wrong_count = row["wrong_answers"] + 1
                conn.execute(
                    "UPDATE knowledge_gaps SET wrong_answers = ?, last_reviewed = ?, difficulty = ? WHERE subject_id = ? AND topic_id = ?",
                    (wrong_count, timestamp, difficulty, subject_id, topic_id)
                )
            else:
                conn.execute(
                    "INSERT INTO knowledge_gaps (subject_id, topic_id, wrong_answers, difficulty, last_reviewed) VALUES (?, ?, 1, ?, ?)",
                    (subject_id, topic_id, difficulty, timestamp)
                )
        else:
            # Mark completed with appropriate confidence
            confidence = int(score / 2.0)  # scale 0-10 score to 1-5 confidence
            confidence = max(1, min(5, confidence))
            conn.execute(
                "INSERT OR REPLACE INTO completed_topics (subject_id, topic_id, completed_at, confidence) VALUES (?, ?, ?, ?)",
                (subject_id, topic_id, timestamp, confidence)
            )
            if confidence >= 4:
                conn.execute(
                    "DELETE FROM knowledge_gaps WHERE subject_id = ? AND topic_id = ?",
                    (subject_id, topic_id)
                )
        conn.commit()
    update_streak(subject_id)

# --- NEW ACADEMIC DASHBOARD HELPERS ---
def update_streak(subject_id: str):
    """Updates learning streak if active on consecutive days."""
    now = datetime.now()
    with get_connection() as conn:
        row = conn.execute("SELECT streak, last_active FROM subjects WHERE subject_id = ?", (subject_id,)).fetchone()
        if not row:
            return
            
        current_streak = row["streak"]
        last_active_str = row["last_active"]
        
        if not last_active_str:
            new_streak = 1
        else:
            try:
                last_active_date = datetime.fromisoformat(last_active_str).date()
                delta = (now.date() - last_active_date).days
                if delta == 1:
                    new_streak = current_streak + 1
                elif delta > 1:
                    new_streak = 1
                else:
                    new_streak = max(1, current_streak) # Same day, streak remains
            except Exception:
                new_streak = 1
                
        conn.execute(
            "UPDATE subjects SET streak = ?, last_active = ? WHERE subject_id = ?",
            (new_streak, now.isoformat(), subject_id)
        )
        conn.commit()

def get_subjects_list() -> List[Dict[str, Any]]:
    """Returns all subjects with progress, streak, average score, and mastery level."""
    init_db()
    results = []
    with get_connection() as conn:
        subjects_rows = conn.execute("SELECT subject_id, subject_name, streak, last_active, mastery_level FROM subjects").fetchall()
        
        for sub in subjects_rows:
            sub_id = sub["subject_id"]
            
            # Count total completed topics
            comp_row = conn.execute("SELECT COUNT(*) FROM completed_topics WHERE subject_id = ?", (sub_id,)).fetchone()
            completed_count = comp_row[0] if comp_row else 0
            
            # Count total curriculum topics to calculate progress %
            curr_rows = conn.execute("SELECT subtopics_json FROM curriculum WHERE subject_id = ?", (sub_id,)).fetchall()
            total_topics = 0
            for curr in curr_rows:
                try:
                    topics = json.loads(curr["subtopics_json"])
                    total_topics += len(topics)
                except Exception:
                    pass
            
            progress_pct = 0
            if total_topics > 0:
                progress_pct = min(100, int((completed_count / total_topics) * 100))
            elif completed_count > 0:
                progress_pct = min(100, int((completed_count / 12) * 100)) # fallback
                
            # Get average score from test_history and viva_history combined
            scores = []
            hist_rows = conn.execute("SELECT score FROM test_history WHERE subject_id = ?", (sub_id,)).fetchall()
            for r in hist_rows:
                scores.append(r["score"])
            viva_rows = conn.execute("SELECT score FROM viva_history WHERE subject_id = ?", (sub_id,)).fetchall()
            for r in viva_rows:
                scores.append(r["score"])
                
            avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
            
            # Determine weak / strong areas
            weak_rows = conn.execute(
                "SELECT topic_id, wrong_answers FROM knowledge_gaps WHERE subject_id = ? ORDER BY wrong_answers DESC LIMIT 3",
                (sub_id,)
            ).fetchall()
            weak_areas = [r["topic_id"] for r in weak_rows]
            
            strong_rows = conn.execute(
                "SELECT topic_id FROM completed_topics WHERE subject_id = ? AND confidence >= 4 LIMIT 3",
                (sub_id,)
            ).fetchall()
            strong_areas = [r["topic_id"] for r in strong_rows]
            
            # Auto-calculate and update mastery level in DB
            mastery = "Novice"
            if progress_pct >= 85 and avg_score >= 8.0:
                mastery = "Expert"
            elif progress_pct >= 40 or avg_score >= 6.0:
                mastery = "Competent"
            
            if mastery != sub["mastery_level"]:
                conn.execute("UPDATE subjects SET mastery_level = ? WHERE subject_id = ?", (mastery, sub_id))
                conn.commit()
                
            results.append({
                "subject_id": sub_id,
                "subject_name": sub["subject_name"],
                "streak": sub["streak"],
                "last_active": sub["last_active"],
                "mastery_level": mastery,
                "completed_count": completed_count,
                "total_topics": total_topics,
                "progress_percent": progress_pct,
                "average_score": avg_score,
                "weak_areas": weak_areas,
                "strong_areas": strong_areas
            })
    return results

def get_curriculum(subject_id: str) -> List[Dict[str, Any]]:
    """Returns curriculum units and chapters for the subject."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT unit_title, chapter_title, subtopics_json FROM curriculum WHERE subject_id = ?",
            (subject_id,)
        ).fetchall()
        
        curriculum_list = []
        for r in rows:
            try:
                subtopics = json.loads(r["subtopics_json"])
            except Exception:
                subtopics = []
            curriculum_list.append({
                "unit_title": r["unit_title"],
                "chapter_title": r["chapter_title"],
                "subtopics": subtopics
            })
        return curriculum_list

def save_curriculum(subject_id: str, units: List[Dict[str, Any]]):
    """Saves the generated curriculum structure to the DB."""
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM curriculum WHERE subject_id = ?", (subject_id,))
        for unit in units:
            unit_title = unit.get("unit_title", "")
            for ch in unit.get("chapters", []):
                chapter_title = ch.get("chapter_title", "")
                subtopics = ch.get("subtopics", [])
                conn.execute(
                    "INSERT INTO curriculum (subject_id, unit_title, chapter_title, subtopics_json) VALUES (?, ?, ?, ?)",
                    (subject_id, unit_title, chapter_title, json.dumps(subtopics))
                )
        conn.commit()

def save_test_result(subject_id: str, topic_id: str, test_type: str, score: float, 
                     correct_count: int, wrong_count: int, skipped_count: int, 
                     time_taken: int, feedback: str):
    """Saves test result to history, updates gaps or completed status, and increments streaks."""
    init_db()
    timestamp = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO test_history (
                subject_id, topic_id, test_type, score, 
                correct_count, wrong_count, skipped_count, 
                time_taken, feedback, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (subject_id, topic_id, test_type, score, correct_count, wrong_count, skipped_count, time_taken, feedback, timestamp))
        
        if score < 6.0:
            difficulty = "Medium" if score >= 4.0 else "High"
            row = conn.execute(
                "SELECT wrong_answers FROM knowledge_gaps WHERE subject_id = ? AND topic_id = ?",
                (subject_id, topic_id)
            ).fetchone()
            
            if row:
                wrong_count_db = row["wrong_answers"] + 1
                conn.execute(
                    "UPDATE knowledge_gaps SET wrong_answers = ?, last_reviewed = ?, difficulty = ? WHERE subject_id = ? AND topic_id = ?",
                    (wrong_count_db, timestamp, difficulty, subject_id, topic_id)
                )
            else:
                conn.execute(
                    "INSERT INTO knowledge_gaps (subject_id, topic_id, wrong_answers, difficulty, last_reviewed) VALUES (?, ?, 1, ?, ?)",
                    (subject_id, topic_id, difficulty, timestamp)
                )
        else:
            confidence = int(score / 2.0)
            confidence = max(1, min(5, confidence))
            conn.execute(
                "INSERT OR REPLACE INTO completed_topics (subject_id, topic_id, completed_at, confidence) VALUES (?, ?, ?, ?)",
                (subject_id, topic_id, timestamp, confidence)
            )
            if confidence >= 4:
                conn.execute(
                    "DELETE FROM knowledge_gaps WHERE subject_id = ? AND topic_id = ?",
                    (subject_id, topic_id)
                )
        conn.commit()
    update_streak(subject_id)

# --- LEGACY STATS & READOUTS ---
def get_completed_topics(subject_id: str) -> List[Dict[str, Any]]:
    """Returns a list of all completed topics for a subject."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT topic_id, completed_at, confidence FROM completed_topics WHERE subject_id = ?",
            (subject_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_knowledge_gaps(subject_id: str) -> List[Dict[str, Any]]:
    """Returns a list of current knowledge gaps for a subject."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT topic_id, wrong_answers, difficulty, last_reviewed FROM knowledge_gaps WHERE subject_id = ?",
            (subject_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_academic_summary() -> Dict[str, Any]:
    """Compiles a full dashboard statistics dictionary for VOID-AIS."""
    init_db()
    subject_id = get_profile_value("current_subject", "dsa")
    chapter = get_profile_value("current_chapter", "basics")
    
    with get_connection() as conn:
        # Get human readable subject name if possible
        subj_row = conn.execute("SELECT subject_name FROM subjects WHERE subject_id = ?", (subject_id,)).fetchone()
        subject_name = subj_row["subject_name"] if subj_row else subject_id.upper().replace("_", " ")
        
        completed_count = conn.execute("SELECT COUNT(*) FROM completed_topics WHERE subject_id = ?", (subject_id,)).fetchone()[0]
        gaps_count = conn.execute("SELECT COUNT(*) FROM knowledge_gaps WHERE subject_id = ?", (subject_id,)).fetchone()[0]
        
        # Count viva score and tests
        scores = []
        hist_rows = conn.execute("SELECT score FROM test_history WHERE subject_id = ?", (subject_id,)).fetchall()
        for r in hist_rows:
            scores.append(r["score"])
        viva_rows = conn.execute("SELECT score FROM viva_history WHERE subject_id = ?", (subject_id,)).fetchall()
        for r in viva_rows:
            scores.append(r["score"])
            
        viva_count = len(viva_rows) + len(hist_rows)
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        
        # Get weak topics list
        weak_rows = conn.execute(
            "SELECT topic_id, wrong_answers FROM knowledge_gaps WHERE subject_id = ? ORDER BY wrong_answers DESC LIMIT 5",
            (subject_id,)
        ).fetchall()
        weak_areas = [f"{r['topic_id']} ({r['wrong_answers']} struggles)" for r in weak_rows]
        
    return {
        "current_subject": subject_name,
        "current_subject_id": subject_id,
        "current_chapter": chapter.title().replace("_", " "),
        "completed_count": completed_count,
        "gaps_count": gaps_count,
        "vivas_taken": viva_count,
        "average_score": avg_score,
        "weak_areas": weak_areas
    }

# --- SPACED REPETITION & STUDY SCHEDULER ---

def add_flashcard(subject_id: str, topic_id: str, front: str, back: str) -> bool:
    """Creates a new flashcard in the database with defaults."""
    init_db()
    next_review = datetime.now().date().isoformat()
    with get_connection() as conn:
        try:
            conn.execute("""
                INSERT INTO flashcards (subject_id, topic_id, front, back, interval, repetitions, ease_factor, next_review)
                VALUES (?, ?, ?, ?, 1, 0, 2.5, ?)
            """, (subject_id, topic_id, front, back, next_review))
            conn.commit()
            return True
        except Exception:
            return False

def get_due_flashcards(subject_id: str = None) -> List[Dict[str, Any]]:
    """Returns a list of due flashcards for study (today or past due dates)."""
    init_db()
    today_str = datetime.now().date().isoformat()
    query = "SELECT id, subject_id, topic_id, front, back, interval, repetitions, ease_factor, next_review FROM flashcards WHERE next_review <= ?"
    params = [today_str]
    
    if subject_id:
        query += " AND subject_id = ?"
        params.append(subject_id)
        
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

def review_flashcard(card_id: int, quality: int) -> Dict[str, Any]:
    """
    Applies the SM-2 Spaced Repetition algorithm based on the user response quality.
    quality: 0 (blackout) to 5 (perfect recall).
    """
    init_db()
    with get_connection() as conn:
        card = conn.execute(
            "SELECT interval, repetitions, ease_factor FROM flashcards WHERE id = ?",
            (card_id,)
        ).fetchone()
        
        if not card:
            return {"status": "error", "message": "Flashcard not found."}
            
        interval = card["interval"]
        repetitions = card["repetitions"]
        ease_factor = card["ease_factor"]
        
        # SM-2 calculation
        if quality < 3:
            # Failed to remember, reset interval and repetitions
            repetitions = 0
            interval = 1
        else:
            # Correct recall
            if repetitions == 0:
                interval = 1
            elif repetitions == 1:
                interval = 6
            else:
                interval = round(interval * ease_factor)
            repetitions += 1
            
        # Adjust ease factor
        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if ease_factor < 1.3:
            ease_factor = 1.3
            
        next_review_date = (datetime.now().date() + timedelta(days=interval)).isoformat()
        
        conn.execute("""
            UPDATE flashcards 
            SET interval = ?, repetitions = ?, ease_factor = ?, next_review = ?
            WHERE id = ?
        """, (interval, repetitions, ease_factor, next_review_date, card_id))
        conn.commit()
        
        return {
            "status": "ok",
            "card_id": card_id,
            "next_interval": interval,
            "next_review": next_review_date,
            "ease_factor": ease_factor
        }

def generate_study_schedule(subject_id: str = None) -> List[Dict[str, Any]]:
    """
    Generates a prioritized study schedule for the user.
    Sorts topics based on:
    1. Due flashcards (Priority 3)
    2. Knowledge gaps / struggles count (Priority 2)
    3. Uncompleted chapters/topics in curriculum (Priority 1)
    """
    init_db()
    
    if not subject_id:
        subject_id = get_profile_value("current_subject", "dsa")
        
    schedule = []
    
    # 1. Fetch due flashcards topics count
    due_cards = get_due_flashcards(subject_id)
    due_topics_counts = {}
    for c in due_cards:
        t = c["topic_id"]
        due_topics_counts[t] = due_topics_counts.get(t, 0) + 1
        
    # 2. Fetch knowledge gaps
    gaps = get_knowledge_gaps(subject_id)
    gaps_map = {g["topic_id"]: g for g in gaps}
    
    # 3. Fetch completed topics
    completed = {c["topic_id"] for c in get_completed_topics(subject_id)}
    
    # 4. Fetch curriculum structure
    curriculum = get_curriculum(subject_id)
    
    # Traverse curriculum and rate each chapter's priority
    for item in curriculum:
        chapter = item["chapter_title"]
        unit = item["unit_title"]
        subtopics = item["subtopics"]
        
        for topic in subtopics:
            is_completed = topic in completed
            due_cards_count = due_topics_counts.get(topic, 0)
            gap_info = gaps_map.get(topic)
            struggles = gap_info["wrong_answers"] if gap_info else 0
            
            # Priority classification:
            # 0: Completed & No cards due (Low)
            # 1: Not completed (Normal)
            # 2: Knowledge Gap / Struggles (High)
            # 3: Due Flashcards (Critical)
            if due_cards_count > 0:
                priority_val = 3
                priority_label = "Critical Review (Due Flashcards)"
            elif struggles > 0:
                priority_val = 2
                priority_label = f"High Priority (Struggling: {struggles} errors)"
            elif not is_completed:
                priority_val = 1
                priority_label = "Standard Study (New Topic)"
            else:
                priority_val = 0
                priority_label = "Completed (No reviews due)"
                
            schedule.append({
                "unit": unit,
                "chapter": chapter,
                "topic": topic,
                "priority_val": priority_val,
                "priority_label": priority_label,
                "due_flashcards": due_cards_count,
                "struggles": struggles,
                "completed": is_completed
            })
            
    # Sort schedule by priority value descending, then struggles descending
    schedule.sort(key=lambda x: (-x["priority_val"], -x["struggles"], x["topic"]))
    return schedule

# Make sure tables exist on load
init_db()
