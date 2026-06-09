import unittest
import os
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date, timedelta

import tools.academic_progress as acad_db
from server.backend.academic_rag import extract_text_from_file

TEST_ACAD_DB = Path(__file__).parent / "memory" / "test_academic_progress.db"

class TestAcademicUpgrade(unittest.TestCase):
    def setUp(self):
        # Override DB path for acad_db
        self.original_db = acad_db.DB_PATH
        acad_db.DB_PATH = TEST_ACAD_DB
        
        TEST_ACAD_DB.parent.mkdir(parents=True, exist_ok=True)
        if TEST_ACAD_DB.exists():
            try:
                TEST_ACAD_DB.unlink()
            except Exception:
                pass
                
        acad_db.init_db()

    def tearDown(self):
        # Restore DB path
        acad_db.DB_PATH = self.original_db
        if TEST_ACAD_DB.exists():
            try:
                TEST_ACAD_DB.unlink()
            except Exception:
                pass

    def test_spaced_repetition_sm2(self):
        subject = "maths"
        topic = "calculus"
        
        # 1. Add card
        ok = acad_db.add_flashcard(subject, topic, "What is the derivative of x^2?", "2x")
        self.assertTrue(ok)
        
        # Verify card created with default values
        cards = acad_db.get_due_flashcards(subject)
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["interval"], 1)
        self.assertEqual(card["repetitions"], 0)
        self.assertEqual(card["ease_factor"], 2.5)
        
        # 2. Review card quality = 4 (correct after hesitation)
        res = acad_db.review_flashcard(card["id"], 4)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["next_interval"], 1) # First recall interval is 1
        
        # Retrieve card to check repetitions
        conn = sqlite3.connect(str(TEST_ACAD_DB))
        cursor = conn.cursor()
        cursor.execute("SELECT interval, repetitions, ease_factor FROM flashcards WHERE id = ?", (card["id"],))
        updated_card = cursor.fetchone()
        self.assertEqual(updated_card[1], 1) # repetitions=1
        
        # 3. Review again quality = 4 -> repetitions=2, interval=6
        res2 = acad_db.review_flashcard(card["id"], 4)
        self.assertEqual(res2["next_interval"], 6)
        
        # Check repetitions
        cursor.execute("SELECT interval, repetitions, ease_factor FROM flashcards WHERE id = ?", (card["id"],))
        updated_card2 = cursor.fetchone()
        self.assertEqual(updated_card2[1], 2) # repetitions=2
        
        # 4. Review quality = 0 (failure) -> should reset
        res3 = acad_db.review_flashcard(card["id"], 0)
        self.assertEqual(res3["next_interval"], 1)
        cursor.execute("SELECT interval, repetitions, ease_factor FROM flashcards WHERE id = ?", (card["id"],))
        reset_card = cursor.fetchone()
        self.assertEqual(reset_card[1], 0) # repetitions reset to 0
        conn.close()

    def test_study_scheduler_priorities(self):
        subject = "oop"
        
        # Create some curriculum
        units_data = [
            {
                "unit_title": "Unit 1: Fundamentals",
                "chapters": [
                    {
                        "chapter_title": "Chapter 1: Classes",
                        "subtopics": ["inheritance", "polymorphism", "encapsulation"]
                    }
                ]
            }
        ]
        acad_db.save_curriculum(subject, units_data)
        
        # Topic 1: completed, no due cards -> priority 0
        timestamp = date.today().isoformat()
        acad_db.mark_topic_completed(subject, "inheritance", confidence=5)
        
        # Topic 2: uncompleted -> priority 1
        # (polymorphism left uncompleted)
        
        # Topic 3: knowledge gap / struggles -> priority 2
        acad_db.record_knowledge_gap(subject, "encapsulation", difficulty="High")
        
        # Fetch schedule
        schedule = acad_db.generate_study_schedule(subject)
        
        # We expect encapsulation (struggling) first, then polymorphism (uncompleted), then inheritance (completed)
        self.assertEqual(schedule[0]["topic"], "encapsulation")
        self.assertEqual(schedule[0]["priority_val"], 2)
        
        self.assertEqual(schedule[1]["topic"], "polymorphism")
        self.assertEqual(schedule[1]["priority_val"], 1)
        
        self.assertEqual(schedule[2]["topic"], "inheritance")
        self.assertEqual(schedule[2]["priority_val"], 0)

    def test_pptx_extraction(self):
        # Create a dummy PPTX zip file
        test_pptx_path = Path(__file__).parent / "test_presentation.pptx"
        
        try:
            with zipfile.ZipFile(test_pptx_path, 'w') as zip_ref:
                # Add slide1 XML
                slide1_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                    <p:cSld>
                        <p:spTree>
                            <p:sp>
                                <p:txBody>
                                    <a:p>
                                        <a:r>
                                            <a:t>Hello Slide Title</a:t>
                                        </a:r>
                                    </a:p>
                                </p:txBody>
                            </p:sp>
                        </p:spTree>
                    </p:cSld>
                </p:sld>
                """
                zip_ref.writestr("ppt/slides/slide1.xml", slide1_xml)
                
            # Run extraction
            extracted_text = extract_text_from_file(test_pptx_path)
            self.assertIn("Hello Slide Title", extracted_text)
        finally:
            if test_pptx_path.exists():
                try:
                    test_pptx_path.unlink()
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
