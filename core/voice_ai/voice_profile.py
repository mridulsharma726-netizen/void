import os
import json
from pathlib import Path
from typing import Dict, Any

ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT_DIR / "memory" / "data" / "voice_config.json"

PERSONALITIES = {
    "Professional": {
        "tag": "PROFESSIONAL",
        "rate": 175,
        "description": "Standard cybernetic guide, respectful, clear, and task-oriented.",
        "prompt_modifier": "\nPERSONALITY: Professional. You are a highly professional cybernetic AI assistant. Keep responses polite, structured, and clear. Address the user as 'Sir' or 'Master Mridul'."
    },
    "Teacher": {
        "tag": "TEACHER",
        "rate": 155,
        "description": "Patient, educational explanation style, uses analogies.",
        "prompt_modifier": "\nPERSONALITY: Teacher. You are a patient, encouraging academic tutor. Explain complex concepts using intuitive analogies and breakdown steps. Ensure the user grasps the basics first."
    },
    "Founder": {
        "tag": "FOUNDER",
        "rate": 190,
        "description": "Action-oriented, startup-minded, focuses on product/business value.",
        "prompt_modifier": "\nPERSONALITY: Founder. You are a strategic, product-oriented tech founder. Prioritize shipping value fast, efficiency, scalability, and user growth. Keep explanations pragmatic."
    },
    "Developer": {
        "tag": "DEVELOPER",
        "rate": 180,
        "description": "Code-first, highly technical, explains complexity details.",
        "prompt_modifier": "\nPERSONALITY: Developer. You are an expert systems engineer. Speak directly in code examples, architecture patterns, and algorithmic complexity (Big O). Skip high-level summaries."
    },
    "Motivator": {
        "tag": "MOTIVATOR",
        "rate": 205,
        "description": "High energy, encourages focus and streaks.",
        "prompt_modifier": "\nPERSONALITY: Motivator. You are an energetic productivity coach. Push the user to maintain their focus session, keep up their streaks, and overcome coding hurdles with positive, high-power encouragement."
    },
    "Researcher": {
        "tag": "RESEARCHER",
        "rate": 165,
        "description": "Scientific rigor, relies on literature references, highly detail-oriented.",
        "prompt_modifier": "\nPERSONALITY: Researcher. You are a rigorous computer science researcher. Rely on formal documentation, cite standards (RFCs, PEPs), and detail academic findings rather than general practices."
    }
}

class VoiceProfileManager:
    def __init__(self):
        self.active_personality = "Professional"
        self.load_config()

    def load_config(self):
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_personality = data.get("active_personality", "Professional")
                    if self.active_personality not in PERSONALITIES:
                        self.active_personality = "Professional"
            else:
                self.save_config()
        except Exception:
            pass

    def save_config(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"active_personality": self.active_personality}, f, indent=2)
        except Exception:
            pass

    def set_personality(self, name: str) -> Dict[str, Any]:
        if name in PERSONALITIES:
            self.active_personality = name
            self.save_config()
            return {"status": "ok", "message": f"Personality switched to {name}.", "active": name}
        return {"status": "error", "message": f"Unknown personality: {name}"}

    def get_prompt_modifier(self) -> str:
        profile = PERSONALITIES.get(self.active_personality, PERSONALITIES["Professional"])
        return profile["prompt_modifier"]

    def get_active_rate(self) -> int:
        profile = PERSONALITIES.get(self.active_personality, PERSONALITIES["Professional"])
        return profile.get("rate", 175)

    def list_personalities(self) -> Dict[str, Any]:
        return {
            "active": self.active_personality,
            "options": {name: val["description"] for name, val in PERSONALITIES.items()}
        }
