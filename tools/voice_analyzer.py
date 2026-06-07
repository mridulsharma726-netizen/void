"""
VOID Voice Characteristics Analyzer
===================================

Performs 100% local, zero-dependency feature extraction on raw mono 16kHz
16-bit signed PCM audio bytes. Estimates fundamental pitch (F0), speech energy,
and Words Per Minute (WPM).
"""

import math
import struct
from typing import Dict, Any, List

def estimate_pitch(audio_bytes: bytes, sample_rate: int = 16000) -> float:
    """
    Estimates the fundamental frequency (pitch) in Hz using Autocorrelation.
    Optimized to scan within typical human ranges (50Hz - 400Hz) with 2x downsampling.
    """
    count = len(audio_bytes) // 2
    if count < 256:
        return 0.0
        
    try:
        # Unpack mono signed 16-bit PCM samples
        samples = struct.unpack(f"{count}h", audio_bytes)
    except Exception:
        return 0.0

    # Human pitch limits mapped to sample lag counts
    min_lag = int(sample_rate / 400) # ~40 samples
    max_lag = int(sample_rate / 50)  # ~320 samples
    
    best_lag = -1
    best_correlation = -1.0
    
    # Analyze window length of 512 samples
    window_len = 512
    
    for lag in range(min_lag, max_lag):
        correlation = 0.0
        sum_sq_x = 0.0
        sum_sq_y = 0.0
        
        limit = min(window_len, count - lag)
        if limit <= 0:
            break
            
        # Downsample index steps to save CPU
        for i in range(0, limit, 2):
            x = samples[i]
            y = samples[i + lag]
            correlation += x * y
            sum_sq_x += x * x
            sum_sq_y += y * y
            
        if sum_sq_x > 0 and sum_sq_y > 0:
            norm_corr = correlation / math.sqrt(sum_sq_x * sum_sq_y)
            if norm_corr > best_correlation:
                best_correlation = norm_corr
                best_lag = lag
                
    # A correlation threshold of 0.4 ensures we check voiced segments
    if best_correlation > 0.4 and best_lag > 0:
        return float(sample_rate / best_lag)
        
    return 0.0

def calculate_rms(audio_bytes: bytes) -> float:
    """Calculates RMS loudness amplitude of signed 16-bit PCM bytes."""
    count = len(audio_bytes) // 2
    if count <= 0:
        return 0.0
    try:
        samples = struct.unpack(f"{count}h", audio_bytes)
        sum_squares = sum(s * s for s in samples)
        return math.sqrt(sum_squares / count)
    except Exception:
        return 0.0

def calculate_wpm(word_count: int, duration_seconds: float) -> float:
    """Calculates Words Per Minute (WPM) speaking rate."""
    if duration_seconds <= 0.3:
        return 0.0
    minutes = duration_seconds / 60.0
    wpm = word_count / minutes
    return round(wpm, 1)

def analyze_audio_segment(audio_bytes: bytes, duration: float, word_count: int) -> Dict[str, Any]:
    """Runs a combined feature extraction sequence on an audio segment."""
    pitch = estimate_pitch(audio_bytes)
    energy = calculate_rms(audio_bytes)
    wpm = calculate_wpm(word_count, duration)
    
    # Categorize energy loudness
    energy_level = "Normal"
    if energy > 4000:
        energy_level = "High"
    elif energy < 600:
        energy_level = "Low"
        
    # Categorize pitch tone
    pitch_level = "Normal"
    if pitch > 200:
        pitch_level = "Elevated"
    elif 0 < pitch < 100:
        pitch_level = "Flat"
        
    return {
        "pitch_hz": round(pitch, 1),
        "pitch_level": pitch_level,
        "energy_rms": round(energy, 1),
        "energy_level": energy_level,
        "wpm": wpm
    }
