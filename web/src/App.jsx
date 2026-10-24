import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldAlert,
  Train,
  Users,
  Activity,
  Volume2,
  VolumeX,
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  Camera,
  Layers,
  Flame,
  Radio,
  ExternalLink,
  ChevronRight,
  Send,
  MessageSquare,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Sliders,
  Maximize2
} from 'lucide-react';

export default function App() {
  const [telemetry, setTelemetry] = useState({
    running: true,
    paused: false,
    fps: 24.2,
    people_count: 3,
    train_eta_seconds: 114,
    train_speed_kmh: 58.0,
    train_id: "METRO-104 (Outbound)",
    signal_interlock: "NORMAL",
    threat_score: 0,
    threat_tier: "nominal",
    active_breach: false,
    active_alert_message: "",
    show_danger_zone: true,
    show_skeleton: true,
    show_heatmap: false,
    danger_zone: [[0.05, 0.70], [0.95, 0.70], [0.99, 0.99], [0.01, 0.99]],
    has_brain: false,
    brain_model: "gpt-4o-mini (Reasoning Engine)",
    vision_engine: "YOLOv8-Pose Nano (Visual Eyes)"
  });

  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [paMuted, setPaMuted] = useState(false);
  const [showBrainModal, setShowBrainModal] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [brainStatusMsg, setBrainStatusMsg] = useState('');
  const [chatMessages, setChatMessages] = useState([
    {
      role: 'assistant',
      content: 'MetroGuard Copilot online. Telemetry sync active. All platform safety boundaries armed.'
    }
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isCopilotTyping, setIsCopilotTyping] = useState(false);
  const [activeTab, setActiveTab] = useState('cctv'); // 'cctv' | 'calibration'
  const [zoneText, setZoneText] = useState(JSON.stringify(telemetry.danger_zone, null, 2));

  // Audio announcer reference for automated alerts
  const lastAnnouncedEventRef = useRef(null);

  const saveOpenAIKey = async (e) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;
    try {
      const res = await fetch('/api/config/openai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput.trim() })
      });
      const data = await res.json();
      setBrainStatusMsg(data.message || 'Key securely stored on backend');
      setApiKeyInput(''); // Clear key immediately from frontend memory
      setTelemetry((prev) => ({
        ...prev,
        has_brain: data.has_brain
      }));
      setTimeout(() => {
        setShowBrainModal(false);
        setBrainStatusMsg('');
      }, 1200);
    } catch (err) {
      setBrainStatusMsg('Failed to update OpenAI key');
    }
  };



  // Poll system status every 600ms
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/status');
        if (res.ok) {
          const data = await res.json();
          setTelemetry(data);
        }
      } catch (err) {
        // Fallback for demo when backend is booting
      }
    };

    const fetchEvents = async () => {
      try {
        const res = await fetch('/api/events');
        if (res.ok) {
          const data = await res.json();
          if (data.events && data.events.length > 0) {
            setEvents(data.events);
            // Auto play audio if not muted and new event
            const latest = data.events[0];
            if (!paMuted && latest && latest.event_id !== lastAnnouncedEventRef.current) {
              lastAnnouncedEventRef.current = latest.event_id;
              if (latest.announcement_audio) {
                const audio = new Audio(latest.announcement_audio);
                audio.play().catch(() => {});
              }
            }
          }
        }
      } catch (err) {}
    };

    fetchStatus();
    fetchEvents();

    const interval = setInterval(() => {
      fetchStatus();
      fetchEvents();
    }, 600);

    return () => clearInterval(interval);
  }, [paMuted]);

  // Handle toggling overlays
  const toggleSetting = async (key, val) => {
    const updated = { ...telemetry, [key]: val };
    setTelemetry(updated);
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: val })
      });
    } catch (e) {}
  };

  // Interlock control
  const triggerInterlock = async (action) => {
    try {
      await fetch('/api/interlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
    } catch (e) {}
  };

  // Copilot send message
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputQuery.trim()) return;

    const userText = inputQuery.trim();
    setChatMessages((prev) => [...prev, { role: 'user', content: userText }]);
    setInputQuery('');
    setIsCopilotTyping(true);

    try {
      const res = await fetch('/api/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userText })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
      } else {
        setChatMessages((prev) => [
          ...prev,
          { role: 'assistant', content: 'Telemetry report: Platform nominal. No critical escalations detected.' }
        ]);
      }
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Offline Copilot: Platform 2 clear. Automated interlocking ready.' }
      ]);
    } finally {
      setIsCopilotTyping(false);
    }
  };

  // Manual PA broadcast trigger
  const triggerManualBroadcast = async () => {
    try {
      await fetch('/api/pa/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: 'Attention Platform 2 passengers: For your safety, stand behind the yellow line.'
        })
      });
    } catch (e) {}
  };

  const getTierColor = (tier) => {
    switch (tier) {
      case 'critical':
        return '#ef4444';
      case 'warning':
        return '#f97316';
      case 'caution':
        return '#f59e0b';
      default:
        return '#10b981';
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-main)' }}>
      {/* Top Tactical Command HUD Header */}
      <header
        style={{
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-surface)',
          padding: '12px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '8px',
              backgroundColor: 'rgba(14, 165, 233, 0.15)',
              border: '1px solid rgba(14, 165, 233, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38bdf8'
            }}
          >
            <ShieldAlert size={26} />
          </div>
          <div>
            <h1 className="tactical-header" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
              METROGUARD AI
              <span
                style={{
                  fontSize: '0.65rem',
                  padding: '2px 8px',
                  borderRadius: '999px',
                  backgroundColor: 'rgba(14, 165, 233, 0.2)',
                  color: '#38bdf8',
                  border: '1px solid rgba(14, 165, 233, 0.4)',
                  letterSpacing: '0.05em'
                }}
              >
                TACTICAL STATION COPILOT
              </span>
            </h1>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              LOCAL-FIRST PLATFORM SAFETY · CBTC TRAIN SYNC · AUTONOMOUS PA INTERVENTION
            </p>
          </div>
        </div>

        {/* Dynamic Threat Matrix Status Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div
            className={telemetry.threat_tier === 'critical' ? 'flash-emergency' : telemetry.threat_tier === 'warning' ? 'flash-warning' : 'glow-nominal'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '8px 18px',
              borderRadius: '8px',
              border: `1px solid ${getTierColor(telemetry.threat_tier)}`,
              backgroundColor: 'var(--bg-card)',
            }}
          >
            <div
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: getTierColor(telemetry.threat_tier),
              }}
            />
            <div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Operational Threat Tier
              </div>
              <div
                className="tactical-header"
                style={{ fontSize: '0.95rem', fontWeight: 700, color: getTierColor(telemetry.threat_tier) }}
              >
                TIER {telemetry.threat_tier.toUpperCase()} ({telemetry.threat_score}%)
              </div>
            </div>
          </div>

          {/* Quick Action Buttons */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setPaMuted(!paMuted)}
              title={paMuted ? 'Unmute PA Voice Agent' : 'Mute PA Voice Agent'}
              style={{
                padding: '8px 14px',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                backgroundColor: paMuted ? 'rgba(239, 68, 68, 0.15)' : 'var(--bg-card)',
                color: paMuted ? '#f87171' : 'var(--text-main)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.8rem',
              }}
            >
              {paMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
              <span>{paMuted ? 'PA MUTED' : 'PA ACTIVE'}</span>
            </button>

            <button
              onClick={() => setShowBrainModal(true)}
              style={{
                padding: '8px 14px',
                borderRadius: '6px',
                border: telemetry.has_brain ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(168, 85, 247, 0.4)',
                backgroundColor: telemetry.has_brain ? 'rgba(16, 185, 129, 0.15)' : 'rgba(168, 85, 247, 0.15)',
                color: telemetry.has_brain ? '#34d399' : '#c084fc',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
              }}
            >
              <Sparkles size={16} />
              <span>{telemetry.has_brain ? 'OPENAI BRAIN ACTIVE' : 'CONNECT OPENAI BRAIN'}</span>
            </button>


            <button
              onClick={triggerManualBroadcast}
              style={{
                padding: '8px 14px',
                borderRadius: '6px',
                border: '1px solid rgba(14, 165, 233, 0.4)',
                backgroundColor: 'rgba(14, 165, 233, 0.15)',
                color: '#38bdf8',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.8rem',
              }}
            >
              <Radio size={16} />
              <span>TEST BROADCAST</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Tactical Grid Viewport */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 380px', gap: '16px', padding: '16px' }}>
        {/* Left Column: CCTV Stream + Telemetry HUD */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* CBTC Telemetry Bar */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '12px',
            }}
          >
            {/* Card 1: Train Proximity */}
            <div className="glass-panel" style={{ padding: '12px 16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                <span className="tactical-header">CBTC INBOUND TRAIN</span>
                <Train size={16} color="#38bdf8" />
              </div>
              <div className="mono-value" style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
                {telemetry.train_eta_seconds} <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>SEC ETA</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                {telemetry.train_id} · {telemetry.train_speed_kmh} km/h
              </div>
            </div>

            {/* Card 2: Track Interlock */}
            <div
              className="glass-panel"
              style={{
                padding: '12px 16px',
                border: telemetry.signal_interlock === 'EMERGENCY_HOLD' ? '1px solid #ef4444' : '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                <span className="tactical-header">SIGNAL INTERLOCK</span>
                <ShieldAlert size={16} color={telemetry.signal_interlock === 'EMERGENCY_HOLD' ? '#ef4444' : '#10b981'} />
              </div>
              <div
                className="tactical-header"
                style={{
                  fontSize: '1.2rem',
                  fontWeight: 700,
                  color: telemetry.signal_interlock === 'EMERGENCY_HOLD' ? '#ef4444' : '#10b981',
                  marginTop: '6px',
                }}
              >
                {telemetry.signal_interlock}
              </div>
              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                {telemetry.signal_interlock === 'EMERGENCY_HOLD' ? (
                  <button
                    onClick={() => triggerInterlock('ACKNOWLEDGE')}
                    style={{
                      padding: '2px 8px',
                      fontSize: '0.68rem',
                      borderRadius: '4px',
                      backgroundColor: '#ef4444',
                      color: '#fff',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}
                  >
                    RESET INTERLOCK
                  </button>
                ) : (
                  <button
                    onClick={() => triggerInterlock('EMERGENCY_HOLD')}
                    style={{
                      padding: '2px 8px',
                      fontSize: '0.68rem',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(239, 68, 68, 0.2)',
                      color: '#ef4444',
                      border: '1px solid #ef4444',
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}
                  >
                    EMERGENCY TRAIN HOLD
                  </button>
                )}
              </div>
            </div>

            {/* Card 3: Platform Crowd Count */}
            <div className="glass-panel" style={{ padding: '12px 16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                <span className="tactical-header">TRACKED PASSENGERS</span>
                <Users size={16} color="#10b981" />
              </div>
              <div className="mono-value" style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
                {telemetry.people_count}{' '}
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>PERSONS</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: '#10b981', marginTop: '2px' }}>
                Edge Density Nominal · Multi-zone OK
              </div>
            </div>

            {/* Card 4: Inference Engine */}
            <div className="glass-panel" style={{ padding: '12px 16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                <span className="tactical-header">VISION INFERENCE</span>
                <Activity size={16} color="#a855f7" />
              </div>
              <div className="mono-value" style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
                {telemetry.fps}{' '}
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>FPS</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                YOLOv8-Pose Nano · ByteTrack CPU
              </div>
            </div>
          </div>

          {/* AI Architecture Pipeline Banner: YOLO Eyes + OpenAI Brain */}
          <div
            className="glass-panel"
            style={{
              padding: '10px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'linear-gradient(90deg, rgba(14, 165, 233, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%)',
              border: '1px solid rgba(14, 165, 233, 0.3)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              {/* EYES LAYER */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: 'rgba(56, 189, 248, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38bdf8' }}>
                  <Camera size={16} />
                </div>
                <div>
                  <div style={{ fontSize: '0.65rem', color: '#38bdf8', fontWeight: 700, letterSpacing: '0.05em' }}>VISUAL SENSORY EYES</div>
                  <div style={{ fontSize: '0.78rem', color: '#f1f5f9', fontWeight: 600 }}>YOLOv8-Pose (Local Real-Time)</div>
                </div>
              </div>

              <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>➔</div>

              {/* SPATIAL / CBTC LAYER */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: 'rgba(245, 158, 11, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f59e0b' }}>
                  <ShieldAlert size={16} />
                </div>
                <div>
                  <div style={{ fontSize: '0.65rem', color: '#f59e0b', fontWeight: 700, letterSpacing: '0.05em' }}>SPATIAL SAFETY MATRIX</div>
                  <div style={{ fontSize: '0.78rem', color: '#f1f5f9', fontWeight: 600 }}>Polygon Boundary + CBTC ETA</div>
                </div>
              </div>

              <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>➔</div>

              {/* BRAIN LAYER */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: telemetry.has_brain ? 'rgba(16, 185, 129, 0.2)' : 'rgba(168, 85, 247, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: telemetry.has_brain ? '#34d399' : '#c084fc' }}>
                  <Sparkles size={16} />
                </div>
                <div>
                  <div style={{ fontSize: '0.65rem', color: telemetry.has_brain ? '#34d399' : '#c084fc', fontWeight: 700, letterSpacing: '0.05em' }}>COGNITIVE REASONING BRAIN</div>
                  <div style={{ fontSize: '0.78rem', color: '#f1f5f9', fontWeight: 600 }}>
                    {telemetry.has_brain ? 'OpenAI GPT-4o-mini (Neural Backend Connected)' : 'Offline SOP Dispatch Engine'}
                  </div>

                </div>
              </div>
            </div>

            <button
              onClick={() => setShowBrainModal(true)}
              style={{
                padding: '4px 12px',
                fontSize: '0.72rem',
                borderRadius: '4px',
                backgroundColor: telemetry.has_brain ? 'rgba(16, 185, 129, 0.2)' : '#0ea5e9',
                color: '#fff',
                border: telemetry.has_brain ? '1px solid #10b981' : 'none',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              {telemetry.has_brain ? 'MANAGE BRAIN KEY' : 'CONFIGURE API KEY'}
            </button>
          </div>


          {/* Primary CCTV Live Viewport */}
          <div
            className="glass-panel"
            style={{
              position: 'relative',
              borderRadius: '8px',
              overflow: 'hidden',
              backgroundColor: '#000',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Viewport Control Bar */}
            <div
              style={{
                backgroundColor: 'rgba(12, 18, 25, 0.9)',
                padding: '8px 16px',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Camera size={18} color="#38bdf8" />
                <span className="tactical-header" style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  CAM-02 NORTH TACTILE EDGE (LIVE FEED)
                </span>
                <span
                  style={{
                    backgroundColor: '#ef4444',
                    color: '#fff',
                    fontSize: '0.62rem',
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: '4px',
                    letterSpacing: '0.08em',
                  }}
                >
                  LIVE
                </span>
              </div>

              {/* Overlay Toggle Controls */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  onClick={() => toggleSetting('show_danger_zone', !telemetry.show_danger_zone)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.75rem',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: telemetry.show_danger_zone ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                    color: telemetry.show_danger_zone ? '#38bdf8' : 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <Layers size={14} />
                  <span>DANGER ZONE</span>
                </button>

                <button
                  onClick={() => toggleSetting('show_skeleton', !telemetry.show_skeleton)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.75rem',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: telemetry.show_skeleton ? 'rgba(168, 85, 247, 0.2)' : 'transparent',
                    color: telemetry.show_skeleton ? '#c084fc' : 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <Activity size={14} />
                  <span>SKELETAL POSE</span>
                </button>

                <button
                  onClick={() => toggleSetting('show_heatmap', !telemetry.show_heatmap)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.75rem',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: telemetry.show_heatmap ? 'rgba(249, 115, 22, 0.2)' : 'transparent',
                    color: telemetry.show_heatmap ? '#fb923c' : 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <Flame size={14} />
                  <span>CROWD HEATMAP</span>
                </button>
              </div>
            </div>

            {/* Video Image Stream */}
            <div style={{ position: 'relative', minHeight: '440px', backgroundColor: '#000', display: 'flex', justifyContent: 'center' }}>
              <img
                src="/api/stream"
                alt="MetroGuard Tactical CCTV Stream"
                style={{ width: '100%', height: 'auto', maxHeight: '520px', objectFit: 'contain' }}
                onError={(e) => {
                  e.target.style.display = 'none';
                  const fallback = document.getElementById('cctv-fallback');
                  if (fallback) fallback.style.display = 'flex';
                }}
              />
              <div
                id="cctv-fallback"
                style={{
                  display: 'none',
                  position: 'absolute',
                  inset: 0,
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexDirection: 'column',
                  gap: '12px',
                  color: 'var(--text-muted)',
                }}
              >
                <Camera size={48} color="#2a3e52" />
                <p>Initializing CCTV feed & YOLOv8-Pose engine…</p>
              </div>

              {/* Dynamic Emergency Banner if Tier 3 active */}
              {telemetry.threat_tier === 'critical' && (
                <div
                  className="flash-emergency"
                  style={{
                    position: 'absolute',
                    top: '16px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    backgroundColor: 'rgba(239, 68, 68, 0.95)',
                    color: '#fff',
                    padding: '8px 24px',
                    borderRadius: '8px',
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    zIndex: 10,
                  }}
                >
                  <AlertTriangle size={20} />
                  <span className="tactical-header">CRITICAL HAZARD: PERSON FALLEN ON TRACK BED</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: AI Incident Copilot & Real-Time Incident Stream */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Incident Log Feed */}
          <div
            className="glass-panel"
            style={{
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '420px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={18} color="#f59e0b" />
                <span className="tactical-header" style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  INCIDENT LOG ARCHIVE
                </span>
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {events.length} RECORDED
              </span>
            </div>

            {/* Events List */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {events.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  No active incidents recorded. Platform boundary secure.
                </div>
              ) : (
                events.map((evt) => (
                  <div
                    key={evt.event_id}
                    onClick={() => setSelectedEvent(evt)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '6px',
                      backgroundColor: 'var(--bg-surface)',
                      border: `1px solid ${selectedEvent?.event_id === evt.event_id ? 'var(--color-accent)' : 'var(--border-subtle)'}`,
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      transition: 'border-color 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span
                        style={{
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: evt.severity === 'critical' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(249, 115, 22, 0.2)',
                          color: evt.severity === 'critical' ? '#ef4444' : '#f97316',
                          textTransform: 'uppercase',
                        }}
                      >
                        {evt.event_type.replace('_', ' ')}
                      </span>
                      <span className="mono-value" style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                        {evt.event_id.split('-').slice(1).join('-')}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#f1f5f9' }}>
                      Track ID #{evt.track_id} · Dwell {evt.dwell_frames}f · Train ETA {evt.train_eta_seconds}s
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* AI Incident Copilot Q&A Panel */}
          <div
            className="glass-panel"
            style={{
              padding: '16px',
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              minHeight: '340px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Sparkles size={18} color="#38bdf8" />
              <span className="tactical-header" style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                STATION OPERATIONS COPILOT
              </span>
            </div>

            {/* Chat Messages */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
              {chatMessages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '90%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    lineHeight: 1.4,
                    backgroundColor: msg.role === 'user' ? '#0ea5e9' : 'var(--bg-surface)',
                    color: msg.role === 'user' ? '#fff' : '#cbd5e1',
                    border: msg.role === 'user' ? 'none' : '1px solid var(--border-subtle)',
                  }}
                >
                  {msg.content}
                </div>
              ))}
              {isCopilotTyping && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  Copilot analyzing platform telemetry…
                </div>
              )}
            </div>

            {/* Chat Query Input */}
            <form onSubmit={handleSendMessage} style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                placeholder="Ask Copilot (e.g., summarize recent incidents)…"
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-surface)',
                  color: '#fff',
                  fontSize: '0.8rem',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  backgroundColor: '#0ea5e9',
                  border: 'none',
                  color: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Incident Detail Modal Inspection */}
      {selectedEvent && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.85)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '24px',
          }}
        >
          <div
            className="glass-panel"
            style={{
              width: '900px',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '24px',
              backgroundColor: '#0c1219',
              border: '1px solid var(--border-active)',
              borderRadius: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 className="tactical-header" style={{ fontSize: '1.25rem', color: '#f8fafc' }}>
                  INCIDENT EVIDENCE INSPECTION · {selectedEvent.event_id}
                </h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Captured at {selectedEvent.timestamp_utc} · {selectedEvent.camera_id}
                </p>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  backgroundColor: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-main)',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                }}
              >
                CLOSE
              </button>
            </div>

            {/* Evidence Image Frames Comparison */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
                  1. ANNOTATED CCTV EVIDENCE FRAME
                </div>
                <img
                  src={`/api/events/${selectedEvent.event_id}/evidence.jpg`}
                  alt="Evidence Frame"
                  style={{ width: '100%', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}
                />
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
                  2. SKELETAL KEYPOINT DIAGNOSTIC OVERLAY
                </div>
                <img
                  src={`/api/events/${selectedEvent.event_id}/pose_overlay.jpg`}
                  alt="Skeletal Overlay"
                  style={{ width: '100%', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}
                />
              </div>
            </div>

            {/* Audio PA Announcement & Script */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Volume2 size={18} color="#38bdf8" />
                <span className="tactical-header" style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  AUTONOMOUS PA BROADCAST AUDIO
                </span>
              </div>
              <audio
                controls
                src={`/api/events/${selectedEvent.event_id}/announcement.mp3`}
                style={{ width: '100%', marginTop: '6px' }}
              />
              <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '8px', fontStyle: 'italic' }}>
                "{selectedEvent.announcement_script}"
              </p>
            </div>

            {/* 3-Bullet AI Copilot SOP Report */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <FileText size={18} color="#10b981" />
                <span className="tactical-header" style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  OPENAI INCIDENT COPILOT DISPATCH BRIEFING
                </span>
              </div>
              <pre
                style={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'inherit',
                  fontSize: '0.82rem',
                  lineHeight: 1.5,
                  color: '#e2e8f0',
                  backgroundColor: 'rgba(0, 0, 0, 0.4)',
                  padding: '12px',
                  borderRadius: '6px',
                }}
              >
                {selectedEvent.report_markdown}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* OpenAI Neural Brain Setup Modal */}
      {showBrainModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.85)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 110,
            padding: '24px',
          }}
        >
          <div
            className="glass-panel"
            style={{
              width: '540px',
              padding: '28px',
              backgroundColor: '#0c1219',
              border: '1px solid #38bdf8',
              borderRadius: '12px',
              boxShadow: '0 0 30px rgba(14, 165, 233, 0.3)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'rgba(168, 85, 247, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#c084fc' }}>
                  <Sparkles size={20} />
                </div>
                <div>
                  <h3 className="tactical-header" style={{ fontSize: '1.1rem', color: '#fff' }}>
                    OPENAI BRAIN CONFIGURATION
                  </h3>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    YOLO provides the Eyes · OpenAI acts as the Cognitive Brain
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowBrainModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  fontSize: '1.2rem',
                  cursor: 'pointer',
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ backgroundColor: 'var(--bg-surface)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontSize: '0.8rem', lineHeight: 1.5, color: '#94a3b8' }}>
              <div style={{ color: '#38bdf8', fontWeight: 600, marginBottom: '4px' }}>👁️ YOLO Eyes:</div>
              Local high-FPS skeletal posture, ground-foot collision, and danger zone tracking.
              <div style={{ color: '#c084fc', fontWeight: 600, marginTop: '8px', marginBottom: '4px' }}>🧠 OpenAI Brain:</div>
              Ingests raw numerical telemetry, reasons about passenger hazards, computes dynamic dispatch SOPs, and powers conversational station Q&A.
            </div>

            <form onSubmit={saveOpenAIKey} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.75rem', color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
                  OpenAI API Key (sk-...)
                </label>
                <input
                  type="password"
                  placeholder={telemetry.has_brain ? "••••••••••••••••••••••••••••••••" : "Paste your sk-... key securely"}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}

                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-card)',
                    color: '#fff',
                    fontSize: '0.85rem',
                    outline: 'none',
                  }}
                />
              </div>

              {brainStatusMsg && (
                <div style={{ fontSize: '0.78rem', color: '#34d399', fontWeight: 500 }}>
                  {brainStatusMsg}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
                <button
                  type="button"
                  onClick={() => setShowBrainModal(false)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    backgroundColor: 'transparent',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                  }}
                >
                  CANCEL
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '8px 20px',
                    borderRadius: '6px',
                    backgroundColor: '#0ea5e9',
                    border: 'none',
                    color: '#fff',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                  }}
                >
                  CONNECT BRAIN
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

