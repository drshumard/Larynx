import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  Calendar
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

// Audio Player Component with scrubbing
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

// Job Detail Modal
const JobDetailModal = ({ job, onClose, onDownload, onDelete }) => {
  const [copied, setCopied] = useState(false);

  const isDone = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const runTime = getJobRunTime(job);

  const requestPayload = {
    endpoint: 'POST /api/jobs',
    body: {
      name: job.name,
      text: `[${job.text_length?.toLocaleString()} characters]`
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{job.name}</h2>
          <button className="modal-close" onClick={onClose}>
            <X />
          </button>
        </div>

        <div className="modal-body">
          {isDone && (
            <div className="detail-section">
              <div className="detail-section-header">
                <Volume2 />
                <span className="detail-section-title">Audio Player</span>
              </div>
              <AudioPlayer jobId={job.id} />
            </div>
          )}

          <div className="detail-section">
            <div className="detail-section-header">
              <Info />
              <span className="detail-section-title">Status</span>
            </div>
            <div className="detail-grid">
              <div className="detail-item">
                <div className="detail-item-label">Status</div>
                <span className={`status-pill ${job.status}`}>{job.status}</span>
              </div>
              <div className="detail-item">
                <div className="detail-item-label">Progress</div>
                <div className="detail-item-value">{job.progress}%</div>
              </div>
              <div className="detail-item">
                <div className="detail-item-label">Stage</div>
                <div className="detail-item-value">{job.stage || '-'}</div>
              </div>
              <div className="detail-item">
                <div className="detail-item-label">Chunks</div>
                <div className="detail-item-value">{job.processed_chunks}/{job.chunk_count}</div>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <div className="detail-section-header">
              <BarChart3 />
              <span className="detail-section-title">Metrics</span>
            </div>
            <div className="detail-grid">
              <div className="detail-item">
                <div className="detail-item-label">Text Length</div>
                <div className="detail-item-value">{job.text_length?.toLocaleString()} chars</div>
              </div>
              <div className="detail-item">
                <div className="detail-item-label">Audio Duration</div>
                <div className="detail-item-value">{job.duration_seconds ? formatDuration(job.duration_seconds) : '-'}</div>
              </div>
              <div className="detail-item">
                <div className="detail-item-label">Processing Time</div>
                <div className="detail-item-value">{runTime || '-'}</div>
              </div>
              <div className="detail-item">
                <div className="detail-item-label">Created</div>
                <div className="detail-item-value">{formatDate(job.created_at)}</div>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <div className="detail-section-header">
              <Terminal />
              <span className="detail-section-title">Request</span>
            </div>
            <div className="code-block">
              <button className="copy-btn" onClick={() => copyToClipboard(JSON.stringify(requestPayload, null, 2))}>
                {copied ? <CheckCircle2 /> : <Copy />}
              </button>
              <pre>{JSON.stringify(requestPayload, null, 2)}</pre>
            </div>
          </div>

          {isFailed && job.error && (
            <div className="detail-section error-section">
              <div className="detail-section-header">
                <AlertCircle />
                <span className="detail-section-title">Error Log</span>
              </div>
              <div className="error-block">
                <pre>{job.error}</pre>
              </div>
            </div>
          )}

          <div className="detail-section">
            <div className="detail-section-header">
              <FileText />
              <span className="detail-section-title">Activity Log</span>
            </div>
            <div className="log-entries">
              <div className="log-entry">
                <span className="log-time">{formatDate(job.created_at)}</span>
                <span className="log-msg">Job created with {job.chunk_count} chunks</span>
              </div>
              {job.status !== 'queued' && (
                <div className="log-entry">
                  <span className="log-time">{formatDate(job.created_at)}</span>
                  <span className="log-msg">Processing started</span>
                </div>
              )}
              {job.processed_chunks > 0 && (
                <div className="log-entry">
                  <span className="log-time">{formatDate(job.updated_at)}</span>
                  <span className="log-msg">Processed {job.processed_chunks} of {job.chunk_count} chunks</span>
                </div>
              )}
              {isDone && (
                <div className="log-entry success">
                  <span className="log-time">{formatDate(job.updated_at)}</span>
                  <span className="log-msg">Job completed — {formatDuration(job.duration_seconds)} audio generated</span>
                </div>
              )}
              {isFailed && (
                <div className="log-entry error">
                  <span className="log-time">{formatDate(job.updated_at)}</span>
                  <span className="log-msg">Job failed: {job.error?.substring(0, 100)}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          {isDone && (
            <button className="btn primary" onClick={() => onDownload(job)}>
              <Download /> Download MP3
            </button>
          )}
          <button className="btn danger" onClick={() => { onDelete(job.id); onClose(); }}>
            <Trash2 /> Delete
          </button>
        </div>
      </div>
    </div>
  );
};

// Main App
function App() {
  const [jobs, setJobs] = useState([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const [selectedJob, setSelectedJob] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(new Date());

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

  const handleDelete = async (jobId) => {
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
      <Toaster position="top-right" toastOptions={{ style: { background: '#0F172A', color: '#fff', border: 'none' } }} />

      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onDownload={handleDownload}
          onDelete={handleDelete}
        />
      )}

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
                          onClick={() => setSelectedJob(job)}
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
                                  <button className="action-btn download" onClick={() => handleDownload(job)} data-testid="job-download-button">
                                    <Download />
                                  </button>
                                </>
                              )}
                              <button className="action-btn delete" onClick={() => handleDelete(job.id)} data-testid="job-delete-button">
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
}

export default App;
