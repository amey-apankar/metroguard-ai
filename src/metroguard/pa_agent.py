"""Autonomous Station Public Address (PA) Voice Agent.

Generates targeted spoken warnings via Edge-TTS with graceful offline fallback.
Supports bilingual warnings (English + Hindi/Regional) and localized details.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


def compose_announcement_text(
    event_type: str,
    track_id: int,
    platform: str = "Platform 2",
    train_id: str = "Train 104",
    train_eta_seconds: int | float | None = None,
    bilingual: bool = True,
) -> str:
    """Compose clear, directional public address warning script."""
    eta_str = f"{int(train_eta_seconds)} seconds" if train_eta_seconds is not None else "approaching"
    
    if event_type == "track_fall":
        en = (
            f"Emergency alert: Person down near track bed on {platform}. "
            f"All passengers stand back. Station marshals dispatching. Train hold requested for {train_id}."
        )
        hi = (
            f"आपातकालीन सूचना: {platform} पर ट्रैक के पास व्यक्ति गिरा हुआ है। "
            f"कृपया तुरंत पीछे हटें। सहायता दल पहुंच रहा है।"
        )
    else:
        en = (
            f"Attention {platform}: Passenger near edge zone, "
            f"please step behind the yellow line immediately. {train_id} is arriving in {eta_str}."
        )
        hi = (
            f"कृपया ध्यान दें {platform}: पीली रेखा के पीछे रहें। "
            f"गाड़ी संख्या {train_id} कुछ ही पलों में आ रही है।"
        )
        
    if bilingual:
        return f"{en} {hi}"
    return en


async def generate_speech_audio(
    text: str,
    output_path: str | Path,
    voice: str = "en-US-ChristopherNeural",
) -> Path | None:
    """Generate TTS audio MP3 using Edge-TTS asynchronously."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_file))
        return out_file
    except Exception:
        # Gracefully handle offline or network restricted environments
        return None


def generate_speech_sync(
    text: str,
    output_path: str | Path,
    voice: str = "en-US-ChristopherNeural",
) -> Path | None:
    """Synchronous helper for TTS generation."""
    try:
        return asyncio.run(generate_speech_audio(text, output_path, voice))
    except Exception:
        return None
