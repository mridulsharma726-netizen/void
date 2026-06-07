"""
VOID Emotional Intelligence Classifier
=====================================

Processes, scores, and updates the estimated emotional state of the user.
Merges lexical keywords (sentiment), acoustic indicators (pitch, energy, WPM),
and behavioral patterns into confidence-based estimates.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("void.emotion_engine")

# Dynamic state tracking the user's current estimated mood
ACTIVE_MOOD = {
    "mood": "Calm",
    "confidence": 85,
    "wpm": 0.0,
    "pitch_hz": 0.0,
    "energy_rms": 0.0,
    "adaptive_state": "Standard"
}

class EmotionEngine:
    """Combines lexical triggers, pitch variables, and WPM speeds into confidence estimates."""
    
    LEXICAL_KEYS = {
        "stressed": ["broken", "fail", "error", "impossible", "hurry", "crash", "stop", "issue", "problem", "fault"],
        "confused": ["how do i", "why", "stuck", "don't get", "explain", "confused", "what is", "help me", "understand"],
        "motivated": ["great", "awesome", "excited", "cool", "want to learn", "teach me", "interested", "perfect", "good"],
        "fatigued": ["tired", "sleepy", "boring", "bored", "whatever", "later", "give up", "sigh", "exhausted"]
    }

    def analyze_lexical_sentiment(self, text: str) -> Dict[str, float]:
        """Calculates keyword match weights for various mood categories."""
        lower = text.lower()
        scores = {"stressed": 0.0, "confused": 0.0, "motivated": 0.0, "fatigued": 0.0}
        
        words = lower.split()
        if not words:
            return scores
            
        for category, keywords in self.LEXICAL_KEYS.items():
            matches = sum(1 for kw in keywords if kw in lower)
            scores[category] = min(1.0, matches / 2.0) # Cap at 1.0
            
        return scores

    def process_turn(self, text: str, voice_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyzes a single turn, updates the ACTIVE_MOOD cache, and returns confidence values."""
        global ACTIVE_MOOD
        
        # 1. Lexical Sentiment
        lexical = self.analyze_lexical_sentiment(text)
        
        # 2. Voice inputs fallback to defaults if not provided (e.g. text mode)
        voice = voice_metrics or {"pitch_hz": 0.0, "pitch_level": "Normal", "energy_rms": 0.0, "energy_level": "Normal", "wpm": 0.0}
        
        wpm = voice.get("wpm", 0.0)
        pitch_level = voice.get("pitch_level", "Normal")
        energy_level = voice.get("energy_level", "Normal")
        
        # 3. Calculate confidence weights
        scores = {
            "Calm": 0.3,
            "Confused": 0.0,
            "Stressed": 0.0,
            "Motivated": 0.0,
            "Fatigued": 0.0
        }
        
        # Stressed adjustments
        scores["Stressed"] += lexical["stressed"] * 0.4
        if wpm > 180:
            scores["Stressed"] += 0.3
        if pitch_level == "Elevated":
            scores["Stressed"] += 0.2
        if energy_level == "High":
            scores["Stressed"] += 0.1
            
        # Confused adjustments
        scores["Confused"] += lexical["confused"] * 0.5
        if 0 < wpm < 100:
            scores["Confused"] += 0.2
        if pitch_level == "Elevated": # rising tone ending
            scores["Confused"] += 0.2
            
        # Motivated adjustments
        scores["Motivated"] += lexical["motivated"] * 0.4
        if 130 <= wpm <= 170:
            scores["Motivated"] += 0.2
        if energy_level == "High":
            scores["Motivated"] += 0.2
            
        # Fatigued adjustments
        scores["Fatigued"] += lexical["fatigued"] * 0.5
        if 0 < wpm < 90:
            scores["Fatigued"] += 0.3
        if pitch_level == "Flat":
            scores["Fatigued"] += 0.2
            
        # Calm baseline adjustments
        if scores["Stressed"] < 0.2 and scores["Confused"] < 0.2 and scores["Fatigued"] < 0.2:
            scores["Calm"] += 0.4
            
        # Select highest scoring emotion
        best_mood = "Calm"
        best_score = 0.0
        for m, s in scores.items():
            if s > best_score:
                best_score = s
                best_mood = m
                
        # Normalize score to percentage (0 - 100)
        confidence_pct = min(99, int(best_score * 100))
        if confidence_pct < 10:
            confidence_pct = 10
            
        # 4. Map adaptive state
        adaptive_state = "Standard"
        if best_mood == "Stressed" and confidence_pct > 60:
            adaptive_state = "Direct Solution"
        elif best_mood == "Confused" and confidence_pct > 55:
            adaptive_state = "Detailed Tutor"
        elif best_mood == "Motivated" and confidence_pct > 65:
            adaptive_state = "Advanced Roadmap"
        elif best_mood == "Fatigued" and confidence_pct > 60:
            adaptive_state = "Encouraging / Brief"
            
        # Update global cache
        ACTIVE_MOOD["mood"] = best_mood
        ACTIVE_MOOD["confidence"] = confidence_pct
        ACTIVE_MOOD["wpm"] = wpm
        ACTIVE_MOOD["pitch_hz"] = voice.get("pitch_hz", 0.0)
        ACTIVE_MOOD["energy_rms"] = voice.get("energy_rms", 0.0)
        ACTIVE_MOOD["adaptive_state"] = adaptive_state
        
        logger.info(f"[MOOD CHANGE ESTIMATE] Mood: {best_mood} ({confidence_pct}%), Adapt: {adaptive_state}")
        return ACTIVE_MOOD

    @staticmethod
    def get_system_prompt_modifier() -> str:
        """Returns the personality override prompt base depending on ACTIVE_MOOD."""
        mood = ACTIVE_MOOD["mood"]
        confidence = ACTIVE_MOOD["confidence"]
        
        if confidence < 50:
            return "" # Don't adapt on low confidence estimates
            
        if mood == "Stressed":
            return (
                "\nADAPTIVE MODE (Direct Solution active): "
                "The user sounds somewhat stressed or frustrated. Avoid any conversational filler, "
                "pleasantries, or long explanations. Focus strictly on direct answers and step-by-step "
                "debugging. Speak in a calm, brief, and reassuring manner."
            )
        elif mood == "Confused":
            return (
                "\nADAPTIVE MODE (Detailed Tutor active): "
                "The user seems a little confused. Explain concepts using real-world analogies, "
                "divide explanations into clear checkpoints, and suggest alternative implementation methods. "
                "Ask a simple question to verify understanding before proceeding."
            )
        elif mood == "Motivated":
            return (
                "\nADAPTIVE MODE (Advanced Roadmap active): "
                "The user seems highly motivated and curious. Suggest advanced optimization options, "
                "explain algorithmic complexity models, and offer deeper engineering details."
            )
        elif mood == "Fatigued":
            return (
                "\nADAPTIVE MODE (Brief active): "
                "The user sounds somewhat tired. Keep responses very short and encouraging. "
                "Suggest taking a short break if they are working on a difficult problem."
            )
        return ""
