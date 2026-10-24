# MetroGuard AI

MetroGuard is a local-first video analytics prototype for Pune Metro station safety use cases. It processes video on the local machine and records structured incident evidence locally. Train telemetry, public address, and train hold actions are simulated in this prototype.

## Current milestone

The first implementation milestone establishes a runnable local video-analysis loop for platform fall and intrusion review. The Pune Metro use-case brief identifies five target areas: platform/track/escalator falls, ticket queue thresholds, loitering or intrusion near Pump Rooms/DG Rooms/fencing, physical encounters, and unattended baggage. The supplied brief provides use-case descriptions and CCTV camera models; it does not include labeled footage, camera calibration, operational thresholds, or live train telemetry. The other four detectors therefore remain planned until suitable footage and thresholds are available.

## Setup

Use Python 3.11 or newer. Create a virtual environment, install `requirements.txt`, and place the supplied YOLO pose weights at `yolov8n-pose.pt` in the project root (or set `METROGUARD_MODEL`).

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Choose a local MP4, set the danger-zone polygon in normalized frame coordinates, and start analysis. The polygon coordinates are editable in `config/cameras.yaml`. Use the included `sample_videos/fall_test.mp4` for a local demonstration when present; media and model weights are excluded from Git.

## Privacy and prototype limits

Video frames and model inference stay on the local machine. Events save to `output/events/`. No OpenAI integration or network upload is enabled by this first milestone. This is an operator decision-support demo, not a certified railway safety system. Any alert and response must be reviewed by a human operator.

## Pune Metro use-case roadmap

1. Platform and track intrusion/fall event detection, local event evidence, and operator dashboard.
2. Camera profiles for escalator falls and configurable station zones.
3. Queue counting and threshold alerts for ticketing areas.
4. Restricted-area entry and loitering alerts.
5. Unattended-object persistence and person/object association.
6. Physical-encounter behavior alerts, validated with representative footage.
7. Optional simulated train ETA, PA, marshal dispatch, and train-hold UI; keep these explicitly simulated.

The Honeywell camera models listed in the supplied brief are Fixed Box HCD8G, Mini Dome H4W8PR2, Bullet HBL6GR2, and PTZ HDZP304DI. Model numbers are reference metadata only; no vendor-specific stream integration is implemented.

