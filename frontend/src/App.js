import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useParams, Link } from 'react-router-dom';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import './App.css';
import { Toaster, toast } from 'sonner';
import {
  Download,
  Loader2,
  Clock,
  FileText,
  Mic,
  AlertCircle,
  RefreshCw,
  Trash2,
  CheckCircle2,
  Volume2,
  XCircle,
  Activity,
  Layers,
  Play,
  Pause,
  BarChart3,
  Info,
  Terminal,
  Copy,
  X,
  Calendar,
  ArrowLeft,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Settings,
  RotateCcw,
  Save
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Helpers
const formatDuration = (seconds) => {
  if (!seconds) return '-';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) return `${hrs}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
};

const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

const getJobRunTime = (job) => {
  if (job.status !== 'completed') return null;
  const start = new Date(job.created_at);
  const end = new Date(job.updated_at);
  const diffMs = end - start;
  const diffMins = Math.floor(diffMs / 60000);
  const diffSecs = Math.floor((diffMs % 60000) / 1000);
  if (diffMins > 0) return `${diffMins}m ${diffSecs}s`;
  return `${diffSecs}s`;
};

// Audio Player Component
const AudioPlayer = ({ jobId }) => {
  const audioRef = useRef(null);
  const trackRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);

  const audioUrl = `${API_URL}/api/jobs/${jobId}/download`;

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current && !isDragging) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
      setIsLoading(false);
    }
  };

  const handleSeek = (e) => {
    if (!trackRef.current || !audioRef.current || !duration) return;
    const rect = trackRef.current.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const newTime = percent * duration;
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const handleMouseDown = (e) => {
    setIsDragging(true);
    handleSeek(e);
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      handleSeek(e);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging]);

  const formatTime = (time) => {
    if (!time || isNaN(time)) return '0:00';
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progressPercent = duration ? (currentTime / duration) * 100 : 0;

  return (
    <div className="audio-player">
      <audio
        ref={audioRef}
        src={audioUrl}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        preload="metadata"
      />

      <button className="play-btn-large" onClick={togglePlay} disabled={isLoading}>
        {isLoading ? (
          <Loader2 className="animate-spin" />
        ) : isPlaying ? (
          <Pause />
        ) : (
          <Play style={{ marginLeft: '2px' }} />
        )}
      </button>

      <div className="player-controls">
        <div
          className="player-track"
          ref={trackRef}
          onMouseDown={handleMouseDown}
        >
          <div
            className="player-progress"
            style={{ width: `${progressPercent}%` }}
          >
            <div className="player-thumb" />
          </div>
        </div>
        <div className="player-times">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  );
};

// Mini Play Button
const MiniPlayButton = ({ jobId }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef(null);

  const togglePlay = (e) => {
    e.stopPropagation();
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        document.querySelectorAll('audio').forEach(a => a.pause());
        audioRef.current.play();
      }
    }
  };

  return (
    <>
      <audio
        ref={audioRef}
        src={`${API_URL}/api/jobs/${jobId}/download`}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />
      <button className="action-btn play" onClick={togglePlay}>
        {isPlaying ? <Pause /> : <Play style={{ marginLeft: '1px' }} />}
      </button>
    </>
  );
};

// Chunk Request Card Component
const ChunkRequestCard = ({ chunk, index, isExpanded, onToggle }) => {
  const [copied, setCopied] = useState(false);
  
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusClass = chunk.status === 'completed' ? 'success' : chunk.status === 'failed' ? 'error' : 'pending';

  return (
    <div className="chunk-card">
      <div className="chunk-header" onClick={onToggle}>
        <div className="chunk-header-left">
          {isExpanded ? <ChevronDown className="chunk-chevron" /> : <ChevronRight className="chunk-chevron" />}
          <span className="chunk-index">Chunk {index + 1}</span>
          <span className={`chunk-status ${statusClass}`}>
            {chunk.status === 'completed' && <CheckCircle2 />}
            {chunk.status === 'failed' && <XCircle />}
            {chunk.status === 'pending' && <Clock />}
            {chunk.status}
          </span>
        </div>
        <div className="chunk-header-right">
          <span className="chunk-meta">{chunk.request?.text_length?.toLocaleString()} chars</span>
          {chunk.processed_at && <span className="chunk-meta">{formatDate(chunk.processed_at)}</span>}
        </div>
      </div>
      
      {isExpanded && (
        <div className="chunk-body">
          <div className="chunk-section">
            <div className="chunk-section-header">
              <Terminal />
              <span>API Request</span>
              <button className="copy-btn-inline" onClick={() => copyToClipboard(JSON.stringify(chunk.request, null, 2))}>
                {copied ? <CheckCircle2 /> : <Copy />}
              </button>
            </div>
            <div className="code-block">
              <pre>{JSON.stringify({
                endpoint: chunk.request?.endpoint,
                voice_id: chunk.request?.voice_id,
                model_id: chunk.request?.model_id,
                output_format: chunk.request?.output_format,
                voice_settings: chunk.request?.voice_settings
              }, null, 2)}</pre>
            </div>
          </div>
          
          <div className="chunk-section">
            <div className="chunk-section-header">
              <FileText />
              <span>Text Content</span>
              <button className="copy-btn-inline" onClick={() => copyToClipboard(chunk.request?.text || '')}>
                {copied ? <CheckCircle2 /> : <Copy />}
              </button>
            </div>
            <div className="text-block">
              <pre>{chunk.request?.text}</pre>
            </div>
          </div>
          
          {chunk.error && (
            <div className="chunk-section">
              <div className="chunk-section-header error">
                <AlertCircle />
                <span>Error</span>
              </div>
              <div className="error-block">
                <pre>{chunk.error}</pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Job Details Page
const JobDetailsPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedChunks, setExpandedChunks] = useState(new Set());
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const fetchJobDetails = async () => {
      try {
        const response = await fetch(`${API_URL}/api/jobs/${jobId}/details`);
        if (response.ok) {
          const data = await response.json();
          setJob(data);
        } else {
          toast.error('Failed to load job details');
          navigate('/');
        }
      } catch (error) {
        toast.error('Failed to load job details');
        navigate('/');
      } finally {
        setLoading(false);
      }
    };

    fetchJobDetails();
  }, [jobId, navigate]);

  const toggleChunk = (index) => {
    const newExpanded = new Set(expandedChunks);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedChunks(newExpanded);
  };

  const expandAll = () => {
    if (job?.chunk_requests) {
      setExpandedChunks(new Set(job.chunk_requests.map((_, i) => i)));
    }
  };

  const collapseAll = () => {
    setExpandedChunks(new Set());
  };

  const copyFullConfig = () => {
    if (job?.tts_config) {
      navigator.clipboard.writeText(JSON.stringify(job.tts_config, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await fetch(`${API_URL}/api/jobs/${jobId}/download`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${job.name.replace(/[^a-zA-Z0-9_-]/g, '_')}.mp3`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        toast.success('Download started');
      }
    } catch (error) {
      toast.error('Failed to download');
    }
  };

  if (loading) {
    return (
      <div className="app">
        <div className="dashboard">
          <div className="loading-state">
            <Loader2 className="animate-spin" />
            <span>Loading job details...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!job) {
    return null;
  }

  const isDone = job.status === 'completed';
  const runTime = getJobRunTime(job);
  const statusClass = job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'processing';

  return (
    <div className="app">
      <div className="dashboard">
        {/* Header */}
        <header className="detail-header">
          <div className="detail-header-left">
            <button className="back-btn" onClick={() => navigate('/')}>
              <ArrowLeft />
            </button>
            <div>
              <h1 className="detail-title">{job.name}</h1>
              <span className="detail-subtitle">Job ID: {job.id}</span>
            </div>
          </div>
          <div className="detail-header-right">
            {isDone && (
              <button className="btn primary" onClick={handleDownload}>
                <Download /> Download MP3
              </button>
            )}
          </div>
        </header>

        {/* Overview Section */}
        <div className="detail-grid-2">
          {/* Job Summary Card */}
          <div className="card">
            <div className="card-header">
              <span className="card-header-icon"><Info /></span>
              <span className="card-title">Job Summary</span>
              <span className={`status-chip ${statusClass}`}>
                {isDone && <CheckCircle2 />}
                {job.status === 'failed' && <XCircle />}
                {statusClass === 'processing' && <Loader2 className="animate-spin" />}
                {job.status}
              </span>
            </div>
            <div className="card-body">
              <div className="summary-grid">
                <div className="summary-item">
                  <span className="summary-label">Text Length</span>
                  <span className="summary-value">{job.text_length?.toLocaleString()} chars</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Chunks</span>
                  <span className="summary-value">{job.processed_chunks} / {job.chunk_count}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Audio Duration</span>
                  <span className="summary-value">{job.duration_seconds ? formatDuration(job.duration_seconds) : '-'}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Processing Time</span>
                  <span className="summary-value">{runTime || '-'}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Created</span>
                  <span className="summary-value">{formatDate(job.created_at)}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Progress</span>
                  <span className="summary-value">{job.progress}%</span>
                </div>
              </div>
              
              {isDone && (
                <div className="summary-player">
                  <AudioPlayer jobId={job.id} />
                </div>
              )}
              
              {job.error && (
                <div className="summary-error">
                  <div className="error-block">
                    <pre>{job.error}</pre>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* TTS Configuration Card */}
          <div className="card">
            <div className="card-header">
              <span className="card-header-icon"><Terminal /></span>
              <span className="card-title">TTS Configuration</span>
              <button className="copy-btn-header" onClick={copyFullConfig}>
                {copied ? <CheckCircle2 /> : <Copy />}
              </button>
            </div>
            <div className="card-body">
              {job.tts_config ? (
                <div className="config-grid">
                  <div className="config-item">
                    <span className="config-label">API Provider</span>
                    <span className="config-value">{job.tts_config.api}</span>
                  </div>
                  <div className="config-item">
                    <span className="config-label">Model</span>
                    <span className="config-value code">{job.tts_config.model_id}</span>
                  </div>
                  <div className="config-item">
                    <span className="config-label">Voice ID</span>
                    <span className="config-value code">{job.tts_config.voice_id}</span>
                  </div>
                  <div className="config-item">
                    <span className="config-label">Output Format</span>
                    <span className="config-value code">{job.tts_config.output_format}</span>
                  </div>
                  <div className="config-item full">
                    <span className="config-label">Voice Settings</span>
                    <div className="config-settings">
                      <span className="setting-badge">stability: {job.tts_config.voice_settings?.stability}</span>
                      <span className="setting-badge">similarity: {job.tts_config.voice_settings?.similarity_boost}</span>
                      <span className="setting-badge accent">speed: {job.tts_config.voice_settings?.speed}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="empty-config">
                  <span>Configuration data not available for this job</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Chunk Requests Section */}
        <div className="card chunks-card">
          <div className="card-header">
            <span className="card-header-icon"><Layers /></span>
            <span className="card-title">Chunk Requests</span>
            <span className="card-badge">{job.chunk_requests?.length || 0}</span>
            <div className="card-header-actions">
              <button className="btn-text" onClick={expandAll}>Expand All</button>
              <button className="btn-text" onClick={collapseAll}>Collapse All</button>
            </div>
          </div>
          <div className="chunks-list">
            {job.chunk_requests && job.chunk_requests.length > 0 ? (
              job.chunk_requests.map((chunk, index) => (
                <ChunkRequestCard
                  key={index}
                  chunk={chunk}
                  index={index}
                  isExpanded={expandedChunks.has(index)}
                  onToggle={() => toggleChunk(index)}
                />
              ))
            ) : (
              <div className="empty-chunks">
                <FileText />
                <span>No chunk request data available for this job</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Settings Modal Component
const SettingsModal = ({ isOpen, onClose, onSave }) => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [jsonView, setJsonView] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/settings`);
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
        setJsonText(JSON.stringify(data, null, 2));
        setJsonError(null);
      }
    } catch (error) {
      toast.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      let settingsToSave = settings;
      
      // If in JSON view, parse the JSON text
      if (jsonView) {
        try {
          settingsToSave = JSON.parse(jsonText);
          setJsonError(null);
        } catch (e) {
          setJsonError('Invalid JSON format');
          setSaving(false);
          return;
        }
      }

      const response = await fetch(`${API_URL}/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsToSave),
      });
      
      if (response.ok) {
        toast.success('Settings saved successfully');
        onSave && onSave();
        onClose();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to save settings');
      }
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/settings/reset`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const data = await response.json();
        setSettings(data.settings);
        setJsonText(JSON.stringify(data.settings, null, 2));
        toast.success('Settings reset to defaults');
      }
    } catch (error) {
      toast.error('Failed to reset settings');
    } finally {
      setSaving(false);
    }
  };

  const updateSetting = (path, value) => {
    setSettings(prev => {
      const newSettings = { ...prev };
      if (path.includes('.')) {
        const [parent, child] = path.split('.');
        newSettings[parent] = { ...newSettings[parent], [child]: value };
      } else {
        newSettings[path] = value;
      }
      setJsonText(JSON.stringify(newSettings, null, 2));
      return newSettings;
    });
  };

  const handleJsonChange = (text) => {
    setJsonText(text);
    try {
      const parsed = JSON.parse(text);
      setSettings(parsed);
      setJsonError(null);
    } catch (e) {
      setJsonError('Invalid JSON');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content settings-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">
            <Settings className="modal-title-icon" />
            TTS Settings
          </h2>
          <div className="modal-header-actions">
            <button 
              className={`view-toggle ${!jsonView ? 'active' : ''}`} 
              onClick={() => setJsonView(false)}
            >
              Form
            </button>
            <button 
              className={`view-toggle ${jsonView ? 'active' : ''}`} 
              onClick={() => setJsonView(true)}
            >
              JSON
            </button>
          </div>
          <button className="modal-close" onClick={onClose}>
            <X />
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div className="settings-loading">
              <Loader2 className="animate-spin" />
              <span>Loading settings...</span>
            </div>
          ) : jsonView ? (
            <div className="json-editor">
              <textarea
                className="json-textarea"
                value={jsonText}
                onChange={(e) => handleJsonChange(e.target.value)}
                spellCheck={false}
              />
              {jsonError && <div className="json-error">{jsonError}</div>}
            </div>
          ) : (
            <div className="settings-form">
              <div className="settings-section">
                <h3 className="settings-section-title">
                  <Terminal />
                  API Configuration
                </h3>
                <div className="settings-grid">
                  <div className="setting-item">
                    <label className="setting-label">Voice ID</label>
                    <input
                      type="text"
                      className="setting-input"
                      value={settings?.voice_id || ''}
                      onChange={(e) => updateSetting('voice_id', e.target.value)}
                      placeholder="ElevenLabs Voice ID"
                    />
                  </div>
                  <div className="setting-item">
                    <label className="setting-label">Model ID</label>
                    <select
                      className="setting-select"
                      value={settings?.model_id || 'eleven_v3'}
                      onChange={(e) => updateSetting('model_id', e.target.value)}
                    >
                      <option value="eleven_v3">eleven_v3 (Latest)</option>
                      <option value="eleven_multilingual_v2">eleven_multilingual_v2</option>
                      <option value="eleven_turbo_v2_5">eleven_turbo_v2_5</option>
                      <option value="eleven_turbo_v2">eleven_turbo_v2</option>
                      <option value="eleven_monolingual_v1">eleven_monolingual_v1</option>
                    </select>
                  </div>
                  <div className="setting-item">
                    <label className="setting-label">Output Format</label>
                    <select
                      className="setting-select"
                      value={settings?.output_format || 'mp3_44100_128'}
                      onChange={(e) => updateSetting('output_format', e.target.value)}
                    >
                      <option value="mp3_44100_128">MP3 44.1kHz 128kbps</option>
                      <option value="mp3_44100_192">MP3 44.1kHz 192kbps</option>
                      <option value="mp3_22050_32">MP3 22.05kHz 32kbps</option>
                      <option value="pcm_16000">PCM 16kHz</option>
                      <option value="pcm_22050">PCM 22.05kHz</option>
                      <option value="pcm_24000">PCM 24kHz</option>
                      <option value="pcm_44100">PCM 44.1kHz</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="settings-section">
                <h3 className="settings-section-title">
                  <Volume2 />
                  Voice Settings
                </h3>
                <div className="settings-grid">
                  <div className="setting-item">
                    <label className="setting-label">
                      Stability
                      <span className="setting-hint">Controls consistency (0-1)</span>
                    </label>
                    <div className="setting-slider-group">
                      <input
                        type="range"
                        className="setting-slider"
                        min="0"
                        max="1"
                        step="0.05"
                        value={settings?.voice_settings?.stability || 0.5}
                        onChange={(e) => updateSetting('voice_settings.stability', parseFloat(e.target.value))}
                      />
                      <span className="setting-value">{settings?.voice_settings?.stability?.toFixed(2) || '0.50'}</span>
                    </div>
                  </div>

                  <div className="setting-item">
                    <label className="setting-label">
                      Similarity Boost
                      <span className="setting-hint">Voice match fidelity (0-1)</span>
                    </label>
                    <div className="setting-slider-group">
                      <input
                        type="range"
                        className="setting-slider"
                        min="0"
                        max="1"
                        step="0.05"
                        value={settings?.voice_settings?.similarity_boost || 1}
                        onChange={(e) => updateSetting('voice_settings.similarity_boost', parseFloat(e.target.value))}
                      />
                      <span className="setting-value">{settings?.voice_settings?.similarity_boost?.toFixed(2) || '1.00'}</span>
                    </div>
                  </div>

                  <div className="setting-item">
                    <label className="setting-label">
                      Speed
                      <span className="setting-hint">Playback pace (0.5-2.0)</span>
                    </label>
                    <div className="setting-slider-group">
                      <input
                        type="range"
                        className="setting-slider"
                        min="0.5"
                        max="2"
                        step="0.05"
                        value={settings?.voice_settings?.speed || 1.2}
                        onChange={(e) => updateSetting('voice_settings.speed', parseFloat(e.target.value))}
                      />
                      <span className="setting-value accent">{settings?.voice_settings?.speed?.toFixed(2) || '1.20'}</span>
                    </div>
                  </div>

                  <div className="setting-item">
                    <label className="setting-label">
                      Style
                      <span className="setting-hint">Expressive emphasis (0-1)</span>
                    </label>
                    <div className="setting-slider-group">
                      <input
                        type="range"
                        className="setting-slider"
                        min="0"
                        max="1"
                        step="0.05"
                        value={settings?.voice_settings?.style || 0}
                        onChange={(e) => updateSetting('voice_settings.style', parseFloat(e.target.value))}
                      />
                      <span className="setting-value">{settings?.voice_settings?.style?.toFixed(2) || '0.00'}</span>
                    </div>
                  </div>

                  <div className="setting-item full">
                    <label className="setting-label">
                      Speaker Boost
                      <span className="setting-hint">Extra speaker similarity (increases latency)</span>
                    </label>
                    <label className="setting-toggle">
                      <input
                        type="checkbox"
                        checked={settings?.voice_settings?.use_speaker_boost || false}
                        onChange={(e) => updateSetting('voice_settings.use_speaker_boost', e.target.checked)}
                      />
                      <span className="toggle-slider"></span>
                      <span className="toggle-label">
                        {settings?.voice_settings?.use_speaker_boost ? 'Enabled' : 'Disabled'}
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn secondary" onClick={handleReset} disabled={saving}>
            <RotateCcw /> Reset to Defaults
          </button>
          <button className="btn primary" onClick={handleSave} disabled={saving || jsonError}>
            {saving ? <Loader2 className="animate-spin" /> : <Save />}
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Dashboard Page
const DashboardPage = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [showSettings, setShowSettings] = useState(false);

  const completedJobs = jobs.filter(j => j.status === 'completed');
  const processingJobs = jobs.filter(j => ['queued', 'chunking', 'transcribing', 'merging'].includes(j.status));
  const failedJobs = jobs.filter(j => j.status === 'failed');
  const totalDuration = completedJobs.reduce((acc, j) => acc + (j.duration_seconds || 0), 0);
  const totalChars = completedJobs.reduce((acc, j) => acc + (j.text_length || 0), 0);

  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const estimatedChunks = Math.ceil(charCount / 4500);
  const canSubmit = name.trim() && text.trim().length >= 100 && !isCreating;

  const fetchJobs = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/jobs`);
      if (response.ok) {
        const data = await response.json();
        setJobs(data.jobs || []);
        setLastUpdated(new Date());
      }
    } catch (error) {
      console.error('Error fetching jobs:', error);
    } finally {
      setIsLoadingJobs(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 2000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;

    setIsCreating(true);
    try {
      const response = await fetch(`${API_URL}/api/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), text: text.trim() }),
      });
      if (response.ok) {
        toast.success('Job created successfully');
        setName('');
        setText('');
        fetchJobs();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to create job');
      }
    } catch (error) {
      toast.error('Failed to create job');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDownload = async (job) => {
    try {
      const response = await fetch(`${API_URL}/api/jobs/${job.id}/download`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${job.name.replace(/[^a-zA-Z0-9_-]/g, '_')}.mp3`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        toast.success('Download started');
      }
    } catch (error) {
      toast.error('Failed to download');
    }
  };

  const handleDelete = async (jobId, e) => {
    e.stopPropagation();
    try {
      const response = await fetch(`${API_URL}/api/jobs/${jobId}`, { method: 'DELETE' });
      if (response.ok) {
        toast.success('Job deleted');
        fetchJobs();
      }
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const getStatusClass = (job) => {
    if (job.status === 'completed') return 'success';
    if (job.status === 'failed') return 'error';
    const isStuck = ['queued', 'chunking', 'transcribing', 'merging'].includes(job.status) &&
      (new Date() - new Date(job.updated_at)) > 120000;
    if (isStuck) return 'warning';
    return 'processing';
  };

  const getStatusLabel = (job) => {
    const isStuck = ['queued', 'chunking', 'transcribing', 'merging'].includes(job.status) &&
      (new Date() - new Date(job.updated_at)) > 120000;
    return isStuck ? 'Stuck' : job.status;
  };

  const formatLastUpdated = () => {
    return lastUpdated.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="app">
      <div className="dashboard">
        {/* Header */}
        <header className="header">
          <div className="brand">
            <div className="brand-icon">
              <Volume2 />
            </div>
            <div className="brand-text">
              <h1>Larynx TTS</h1>
              <span>Text-to-Speech Pipeline</span>
            </div>
          </div>
          <div className="header-actions">
            <span className="last-updated">
              <Calendar />
              Updated {formatLastUpdated()}
            </span>
            <button className="refresh-btn" onClick={fetchJobs} data-testid="refresh-button">
              <RefreshCw />
            </button>
          </div>
        </header>

        {/* Metrics Row */}
        <div className="metrics-row">
          <div className="metric-card">
            <div className="metric-label">
              <span>Completed</span>
              <CheckCircle2 />
            </div>
            <div className="metric-value">{completedJobs.length}</div>
            <div className="metric-helper success">Ready for download</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span>Processing</span>
              <Activity />
            </div>
            <div className="metric-value accent">{processingJobs.length}</div>
            <div className="metric-helper">In queue</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span>Failed</span>
              <XCircle />
            </div>
            <div className="metric-value">{failedJobs.length}</div>
            <div className="metric-helper error">{failedJobs.length > 0 ? 'Needs attention' : 'No errors'}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span>Total Audio</span>
              <Clock />
            </div>
            <div className="metric-value">{formatDuration(totalDuration) || '0s'}</div>
            <div className="metric-helper">Generated content</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span>Characters</span>
              <FileText />
            </div>
            <div className="metric-value">{totalChars > 1000 ? `${(totalChars / 1000).toFixed(0)}K` : totalChars}</div>
            <div className="metric-helper">Processed text</div>
          </div>
        </div>

        {/* Main Content */}
        <div className="content-grid">
          {/* Create Job Card */}
          <div className="card create-card">
            <div className="card-header">
              <span className="card-header-icon"><Mic /></span>
              <span className="card-title">Create New Job</span>
            </div>
            <form onSubmit={handleSubmit} className="create-form">
              <div className="form-group">
                <label className="form-label">Project Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., Chapter 1 Narration"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  data-testid="job-name-input"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Text Content</label>
                <textarea
                  className="form-textarea"
                  placeholder="Paste your text here... (minimum 100 characters)"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  data-testid="job-text-textarea"
                />
              </div>
              <div className="form-meta">
                <span className="form-meta-item">{charCount.toLocaleString()} characters</span>
                <span className="form-meta-item">{wordCount.toLocaleString()} words</span>
                {charCount > 100 && <span className="form-meta-item accent">~{estimatedChunks} chunks</span>}
                {charCount > 0 && charCount < 100 && <span className="form-meta-item error">Min 100 chars required</span>}
              </div>
              <button type="submit" className="btn-primary" disabled={!canSubmit} data-testid="create-job-submit-button">
                {isCreating ? (
                  <><Loader2 className="animate-spin" /> Creating...</>
                ) : (
                  <><Play /> Generate Audio</>
                )}
              </button>
            </form>
          </div>

          {/* Jobs Table */}
          <div className="card jobs-card">
            <div className="card-header">
              <span className="card-header-icon"><Layers /></span>
              <span className="card-title">Jobs</span>
              <span className="card-badge">{jobs.length}</span>
              <span className="card-hint">Click row to view details</span>
            </div>

            <div className="table-container">
              {isLoadingJobs && jobs.length === 0 ? (
                <div className="empty-state">
                  <Loader2 className="animate-spin" />
                  <span>Loading jobs...</span>
                </div>
              ) : jobs.length === 0 ? (
                <div className="empty-state" data-testid="jobs-empty-state">
                  <Mic />
                  <span>No jobs yet. Create your first one above.</span>
                </div>
              ) : (
                <table className="jobs-table">
                  <thead>
                    <tr>
                      <th className="col-name">Name</th>
                      <th className="col-size">Size</th>
                      <th className="col-chunks">Chunks</th>
                      <th className="col-audio">Audio</th>
                      <th className="col-time">Time</th>
                      <th className="col-progress">Progress</th>
                      <th className="col-status">Status</th>
                      <th className="col-actions">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => {
                      const statusClass = getStatusClass(job);
                      const isDone = job.status === 'completed';
                      const isFailed = job.status === 'failed';
                      const runTime = getJobRunTime(job);

                      return (
                        <tr
                          key={job.id}
                          onClick={() => navigate(`/job/${job.id}`)}
                          data-testid={`jobs-table-row-${job.id}`}
                        >
                          <td>
                            <div className="cell-name">
                              <div className={`status-dot ${statusClass}`} />
                              <div className="cell-name-content">
                                <span className="job-name" data-testid="job-name-cell">{job.name}</span>
                                {isFailed && <div className="job-subtitle">Click to view error</div>}
                              </div>
                            </div>
                          </td>
                          <td><span className="cell-value">{job.text_length?.toLocaleString()}</span></td>
                          <td><span className="cell-value">{job.chunk_count}</span></td>
                          <td><span className={`cell-value ${!isDone ? 'muted' : ''}`}>{isDone && job.duration_seconds ? formatDuration(job.duration_seconds) : '-'}</span></td>
                          <td><span className={`cell-value ${!runTime ? 'muted' : ''}`}>{runTime || '-'}</span></td>
                          <td>
                            <div className="cell-progress">
                              <div className="progress-bar">
                                <div className={`progress-fill ${statusClass}`} style={{ width: `${job.progress}%` }} />
                              </div>
                              <span className="progress-value">{job.progress}%</span>
                            </div>
                          </td>
                          <td>
                            <span className={`status-chip ${statusClass}`}>
                              {isDone && <CheckCircle2 />}
                              {isFailed && <XCircle />}
                              {statusClass === 'processing' && <Loader2 className="animate-spin" />}
                              {statusClass === 'warning' && <AlertCircle />}
                              {getStatusLabel(job)}
                            </span>
                          </td>
                          <td onClick={e => e.stopPropagation()}>
                            <div className="cell-actions">
                              {isDone && (
                                <>
                                  <MiniPlayButton jobId={job.id} />
                                  <button className="action-btn download" onClick={(e) => { e.stopPropagation(); handleDownload(job); }} data-testid="job-download-button">
                                    <Download />
                                  </button>
                                </>
                              )}
                              <button className="action-btn delete" onClick={(e) => handleDelete(job.id, e)} data-testid="job-delete-button">
                                <Trash2 />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Main App with Router
function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" toastOptions={{ style: { background: '#0F172A', color: '#fff', border: 'none' } }} />
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/job/:jobId" element={<JobDetailsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
