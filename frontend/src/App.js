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

// Audio Player Component with proper scrubbing
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
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : isPlaying ? (
          <Pause className="w-5 h-5" />
        ) : (
          <Play className="w-5 h-5" style={{ marginLeft: '2px' }} />
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

// Mini Play Button for table
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
        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" style={{ marginLeft: '1px' }} />}
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
          <h2>{job.name}</h2>
          <button className="modal-close" onClick={onClose}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="modal-body">
          {isDone && (
            <div className="detail-section">
              <h3><Volume2 className="w-4 h-4" /> Audio Player</h3>
              <AudioPlayer jobId={job.id} />
            </div>
          )}

          <div className="detail-section">
            <h3><Info className="w-4 h-4" /> Status</h3>
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">Status</span>
                <span className={`status-pill ${job.status}`}>{job.status}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Progress</span>
                <span className="detail-value">{job.progress}%</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Stage</span>
                <span className="detail-value">{job.stage || '-'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Chunks</span>
                <span className="detail-value">{job.processed_chunks}/{job.chunk_count}</span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h3><BarChart3 className="w-4 h-4" /> Metrics</h3>
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">Text Length</span>
                <span className="detail-value">{job.text_length?.toLocaleString()} chars</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Audio Duration</span>
                <span className="detail-value">{job.duration_seconds ? formatDuration(job.duration_seconds) : '-'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Processing Time</span>
                <span className="detail-value">{runTime || '-'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Created</span>
                <span className="detail-value">{formatDate(job.created_at)}</span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h3><Terminal className="w-4 h-4" /> Request</h3>
            <div className="code-block">
              <button className="copy-btn" onClick={() => copyToClipboard(JSON.stringify(requestPayload, null, 2))}>
                {copied ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </button>
              <pre>{JSON.stringify(requestPayload, null, 2)}</pre>
            </div>
          </div>

          {isFailed && job.error && (
            <div className="detail-section error-section">
              <h3><AlertCircle className="w-4 h-4" /> Error Log</h3>
              <div className="error-block">
                <pre>{job.error}</pre>
              </div>
            </div>
          )}

          <div className="detail-section">
            <h3><FileText className="w-4 h-4" /> Activity Log</h3>
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
                  <span className="log-msg">Job completed - {formatDuration(job.duration_seconds)} audio generated</span>
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
              <Download className="w-4 h-4" /> Download MP3
            </button>
          )}
          <button className="btn danger" onClick={() => { onDelete(job.id); onClose(); }}>
            <Trash2 className="w-4 h-4" /> Delete
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
        toast.success('Job created successfully!');
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
        toast.success('Download started!');
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
    if (job.status === 'failed') return 'danger';
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
      <Toaster position="top-right" richColors />

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
              <Volume2 className="w-6 h-6" />
            </div>
            <div>
              <h1>Larynx TTS</h1>
              <span>Powered by ElevenLabs v3</span>
            </div>
          </div>
          <div className="header-actions">
            <span className="last-updated">
              <Calendar className="w-4 h-4" />
              Last updated: {formatLastUpdated()}
            </span>
            <button className="refresh-btn" onClick={fetchJobs} data-testid="refresh-button">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Stats Row */}
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-card-header">
              <span>Completed</span>
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div className="stat-value">{completedJobs.length}</div>
            <div className="stat-trend positive">Ready for download</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-header">
              <span>Processing</span>
              <Activity className="w-4 h-4" />
            </div>
            <div className="stat-value">{processingJobs.length}</div>
            <div className="stat-trend neutral">In queue</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-header">
              <span>Failed</span>
              <XCircle className="w-4 h-4" />
            </div>
            <div className="stat-value">{failedJobs.length}</div>
            <div className="stat-trend negative">Needs attention</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-header">
              <span>Total Audio</span>
              <Clock className="w-4 h-4" />
            </div>
            <div className="stat-value">{formatDuration(totalDuration) || '0s'}</div>
            <div className="stat-trend neutral">Generated content</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-header">
              <span>Characters</span>
              <FileText className="w-4 h-4" />
            </div>
            <div className="stat-value">{totalChars > 1000 ? `${(totalChars / 1000).toFixed(0)}K` : totalChars}</div>
            <div className="stat-trend neutral">Processed text</div>
          </div>
        </div>

        {/* Main Content */}
        <div className="main-grid">
          {/* Create Job Card */}
          <div className="card create-card">
            <div className="card-header">
              <Mic className="w-5 h-5" />
              <span>Create New Job</span>
            </div>
            <form onSubmit={handleSubmit} className="create-form">
              <div className="form-group">
                <label>Project Name</label>
                <input
                  type="text"
                  placeholder="e.g., Chapter 1 Narration"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  data-testid="job-name-input"
                />
              </div>
              <div className="form-group">
                <label>Text Content</label>
                <textarea
                  placeholder="Paste your text here... (minimum 100 characters)"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  data-testid="job-text-textarea"
                />
              </div>
              <div className="form-meta">
                <span>{charCount.toLocaleString()} chars</span>
                <span>{wordCount.toLocaleString()} words</span>
                {charCount > 100 && <span className="highlight">~{estimatedChunks} chunks</span>}
                {charCount > 0 && charCount < 100 && <span className="warning">Min 100 chars</span>}
              </div>
              <button type="submit" className="submit-btn" disabled={!canSubmit} data-testid="create-job-submit-button">
                {isCreating ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Creating...</>
                ) : (
                  <><Play className="w-4 h-4" /> Generate Audio</>
                )}
              </button>
            </form>
          </div>

          {/* Jobs Table */}
          <div className="card jobs-card">
            <div className="card-header">
              <Layers className="w-5 h-5" />
              <span>Jobs</span>
              <span className="badge">{jobs.length}</span>
              <span className="hint">Click on a row to view details</span>
            </div>

            <div className="table-container">
              {isLoadingJobs && jobs.length === 0 ? (
                <div className="empty-state">
                  <Loader2 className="w-8 h-8 animate-spin" />
                  <span>Loading jobs...</span>
                </div>
              ) : jobs.length === 0 ? (
                <div className="empty-state" data-testid="jobs-empty-state">
                  <Mic className="w-10 h-10" />
                  <span>No jobs yet. Create your first one!</span>
                </div>
              ) : (
                <table className="jobs-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Size</th>
                      <th>Chunks</th>
                      <th>Audio</th>
                      <th>Time</th>
                      <th>Progress</th>
                      <th>Status</th>
                      <th>Actions</th>
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
                            <div className="name-cell">
                              <div className={`status-indicator ${statusClass}`} />
                              <div className="name-content">
                                <span className="job-name" data-testid="job-name-cell">{job.name}</span>
                                {isFailed && <span className="job-error-hint">Click to view error</span>}
                              </div>
                            </div>
                          </td>
                          <td><span className="cell-value">{job.text_length?.toLocaleString()}</span></td>
                          <td><span className="cell-value">{job.chunk_count}</span></td>
                          <td><span className={`cell-value ${!isDone ? 'cell-muted' : ''}`}>{isDone && job.duration_seconds ? formatDuration(job.duration_seconds) : '-'}</span></td>
                          <td><span className={`cell-value ${!runTime ? 'cell-muted' : ''}`}>{runTime || '-'}</span></td>
                          <td>
                            <div className="progress-cell">
                              <div className="progress-bar">
                                <div className={`progress-fill ${statusClass}`} style={{ width: `${job.progress}%` }} />
                              </div>
                              <span className="progress-text">{job.progress}%</span>
                            </div>
                          </td>
                          <td>
                            <span className={`status-badge ${statusClass}`}>
                              {isDone && <CheckCircle2 className="w-3 h-3" />}
                              {isFailed && <XCircle className="w-3 h-3" />}
                              {statusClass === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                              {statusClass === 'warning' && <AlertCircle className="w-3 h-3" />}
                              {getStatusLabel(job)}
                            </span>
                          </td>
                          <td onClick={e => e.stopPropagation()}>
                            <div className="actions-cell">
                              {isDone && (
                                <>
                                  <MiniPlayButton jobId={job.id} />
                                  <button className="action-btn download" onClick={() => handleDownload(job)} data-testid="job-download-button">
                                    <Download className="w-4 h-4" />
                                  </button>
                                </>
                              )}
                              <button className="action-btn delete" onClick={() => handleDelete(job.id)} data-testid="job-delete-button">
                                <Trash2 className="w-4 h-4" />
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
