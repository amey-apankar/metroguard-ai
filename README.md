# MetroGuard AI — Next-Gen Autonomous Metro Platform Safety Copilot

MetroGuard AI is an operator-grade, local-first safety and incident response co-pilot for metro platform operations. It transforms passive platform CCTV into an **active guardian** that intervenes in the critical 15–30 seconds before potential train impact.

---

## Key Features

1. **Tactical Command Center Dashboard (React + Vite)**:
   - Modern dark-mode high-contrast control-room HUD with real-time telemetry cards (CBTC Train ETA, Signal Interlock status, Passenger counts, Vision inference FPS).
   - Live CCTV stream with toggleable overlays: Danger Zone polygon, YOLOv8 Skeletal Keypoint diagnostics, and Crowd Density Heatmap.
   - Interactive Signal Interlock control (`NORMAL` / `EMERGENCY TRAIN HOLD`).
   - Autonomous Public Address (PA) Voice Agent control with speaker mute/unmute and manual alert broadcast test.

2. **Computer Vision & Skeletal Fall Detection**:
   - **YOLOv8-Pose Nano** running 100% locally on CPU/GPU.
   - **ByteTrack** multi-object persistent tracking across frames.
   - Ground contact foot point calculation & polygon boundary collision detection.
   - Torso angle tilt computation ($> 60^\circ$ orientation) distinguishing slips/falls from upright standing.

3. **CBTC Train Telemetry & Dynamic Threat Matrix**:
   - Dynamic Threat Score ($0 - 100\%$) scaling with posture, zone dwell frames, and approaching train ETA countdown.
   - Automated escalation tiers: Tier 1 (Caution), Tier 2 (Warning), Tier 3 (Critical Emergency).

4. **Autonomous PA Voice Agent & Evidence Packaging**:
   - Bilingual audio warnings synthesized via Edge-TTS / local speech synthesis.
   - Automatic archiving into `output/events/<event_id>/`:
     - `evidence.jpg` (annotated CCTV snapshot)
     - `pose_overlay.jpg` (skeletal diagnostic visualization)
     - `announcement.mp3` (synthesized voice warning)
     - `event.json` (structured machine telemetry)
     - `report.md` (OpenAI 3-bullet SOP incident report)

5. **OpenAI Incident Copilot**:
   - Structured 3-bullet Standard Operating Procedure (SOP) dispatch briefing (`Observed Facts`, `Threat Assessment`, `SOP Action Items`).
   - Interactive Q&A chat for station controllers (e.g. asking for summaries or active threats), with instant offline fallback.

6. **Streamlit Reviewer (Alternative Dashboard)**:
   - File upload or sample video analysis with frame-by-frame progress and event inspector.

---

## Getting Started

### 1. Requirements & Setup
- Python 3.11+
- Node.js 18+ (tested on v24)
- Place `yolov8n-pose.pt` in the project root.

```powershell
# Install Python backend dependencies
pip install -r requirements.txt

# Install Web dashboard dependencies
cd web
npm install
npm run build
cd ..
```

### 2. Launch the Tactical Command Center (Recommended)

Run the unified FastAPI server:
```powershell
python -m metroguard.server
```
Then open your browser to **`http://localhost:8000`** (or run `npm run dev` in `web/` on port 5173 with proxy).

### 3. Launch the Streamlit Inspector (Alternative)

```powershell
streamlit run app.py
```

---

## Demonstration Script & Acceptance Criteria

1. **Nominal State**: Open `http://localhost:8000`. Observe live CCTV feed, train ETA countdown, and green safe platform polygon.
2. **Loitering / Warning**: As passenger lingers near edge, threat level escalates to Amber / Warning with dwell tracking.
3. **Critical Emergency**: When track fall occurs or person enters danger zone with train approaching ($< 45\text{s}$ ETA):
   - HUD flashes red **CRITICAL HAZARD**.
   - Autonomous PA Voice speaks localized warning aloud.
   - Simulated **EMERGENCY TRAIN HOLD** interlock is engaged.
4. **Incident Inspection & AI Copilot**: Click any event in the Incident Log to inspect the dual snapshots (`evidence.jpg` & `pose_overlay.jpg`), listen to the audio broadcast, and review the OpenAI Copilot 3-bullet SOP report.
