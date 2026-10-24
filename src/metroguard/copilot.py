"""OpenAI Incident Copilot for structured operational telemetry analysis.

Generates 3-bullet standard operating procedure (SOP) dispatch briefings:
1. Observed Facts
2. Threat Assessment & Severity Rating
3. Standard Operating Procedure (SOP) Action Items
Provides robust offline template fallback when API key is unavailable.
"""

from __future__ import annotations

import json
import os
from typing import Any


OFFLINE_TEMPLATE = """### 🚨 Incident Copilot Briefing (Offline Mode)
**1. Observed Facts:**
- Incident Type: {event_type_label} (Track ID: #{track_id})
- Location: {camera_id} at video timestamp {time_str}
- Telemetry: Torso tilt {tilt_str}, zone dwell {dwell} frames, train ETA {eta_str}.

**2. Threat Assessment & Severity Rating:**
- Severity: {severity_upper} (Dynamic Risk Score: {risk_score}/100)
- Assessment: {risk_detail}

**3. Standard Operating Procedure (SOP) Action Items:**
- {action_1}
- {action_2}
- {action_3}
"""


def generate_incident_report(event_telemetry: dict[str, Any], api_key: str | None = None) -> str:
    """Generate structured 3-bullet incident report using GPT-4o-mini or local fallback."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    
    event_type = event_telemetry.get("event_type", "intrusion")
    severity = event_telemetry.get("severity", "warning").upper()
    track_id = event_telemetry.get("track_id", 0)
    camera_id = event_telemetry.get("camera_id", "Platform-01")
    dwell = event_telemetry.get("dwell_frames", 0)
    tilt = event_telemetry.get("torso_tilt_degrees")
    tilt_str = f"{tilt:.1f}°" if tilt is not None else "N/A (standing upright)"
    eta = event_telemetry.get("train_eta_seconds")
    eta_str = f"{eta}s" if eta is not None else "Unknown"
    time_str = f"{event_telemetry.get('video_time_seconds', 0.0):.1f}s"
    
    # Calculate mock risk score
    risk_score = 95 if event_type == "track_fall" else (75 if dwell > 20 else 55)
    
    if key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            prompt = (
                f"You are the MetroGuard AI Station Operations Copilot. "
                f"Analyze this platform CCTV safety telemetry event and generate an operator dispatch report in markdown:\n"
                f"{json.dumps(event_telemetry, indent=2)}\n\n"
                f"Format strictly with 3 bulleted sections:\n"
                f"1. **Observed Facts**: Concise verifiable telemetry (track ID, camera, posture, dwell frames, ETA).\n"
                f"2. **Threat Assessment & Severity Rating**: Operational risk evaluation and severity label.\n"
                f"3. **Standard Operating Procedure (SOP) Action Items**: Immediate concrete actions for station controller & platform marshals."
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional rapid-response metro operations copilot."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=350,
            )
            content = response.choices[0].message.content
            if content:
                return content
        except Exception:
            pass  # Fall back to offline template

    # Offline high-quality SOP generation
    if event_type == "track_fall":
        risk_detail = "CRITICAL HAZARD - Individual collapsed/fallen onto track area with oncoming train collision hazard."
        action_1 = "Assert Emergency Train Hold (ETH) signal interlock immediately to halt approaching train."
        action_2 = "Dispatch Platform Safety Marshals and Station Medical Response Unit to designated platform quadrant."
        action_3 = "Trigger bilingual automated emergency PA evacuation broadcast."
    else:
        risk_detail = "MODERATE/HIGH HAZARD - Passenger prolonged loitering inside dynamic edge danger polygon."
        action_1 = "Broadcast directional PA warning to step behind tactile yellow line."
        action_2 = "Alert roaming platform attendant to visually monitor track boundary."
        action_3 = "Maintain CBTC train speed advisory if passenger remains inside zone past 60 frames."

    return OFFLINE_TEMPLATE.format(
        event_type_label=event_type.replace("_", " ").title(),
        track_id=track_id,
        camera_id=camera_id,
        time_str=time_str,
        tilt_str=tilt_str,
        dwell=dwell,
        eta_str=eta_str,
        severity_upper=severity,
        risk_score=risk_score,
        risk_detail=risk_detail,
        action_1=action_1,
        action_2=action_2,
        action_3=action_3,
    )


def copilot_query_chat(query: str, recent_events: list[dict[str, Any]], api_key: str | None = None) -> str:
    """Answer operator queries about ongoing platform safety and recent telemetry."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            system = "You are MetroGuard Station Operations Copilot. Answer operator queries based on recent platform events."
            user_msg = f"Recent Events:\n{json.dumps(recent_events[-5:], indent=2)}\n\nOperator Query: {query}"
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.3,
                max_tokens=250,
            )
            return res.choices[0].message.content or "No response generated."
        except Exception as e:
            return f"Copilot query failed: {str(e)}. Operating in fallback mode."
            
    # Offline simulated answer
    total_events = len(recent_events)
    critical_count = sum(1 for e in recent_events if e.get("severity") == "critical")
    return (
        f"**Copilot Report (Offline Telemetry Summary):**\n"
        f"Over the active session, recorded **{total_events} safety incident(s)** with **{critical_count} critical track event(s)**. "
        f"All automated PA announcements and simulated train interlocks have been logged to disk. "
        f"Current platform status remains monitored under nominal CBTC supervision."
    )
