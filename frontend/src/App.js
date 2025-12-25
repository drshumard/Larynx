import React, { useState, useEffect, useCallback } from 'react';
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
  Zap,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Info,
  Terminal,
  Copy,
  X
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Helpers
const formatDuration = (seconds) => {
  if (!seconds) return '0:00';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) return `${hrs}h ${mins}m`;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
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
      text: `[${job.text_length} characters]`
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
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="modal-body">
          {/* Status Section */}
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
          
          {/* Metrics Section */}
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
          
          {/* Request Section */}
          <div className="detail-section">
            <h3><Terminal className="w-4 h-4" /> Request</h3>
            <div className="code-block">
              <button className="copy-btn" onClick={() => copyToClipboard(JSON.stringify(requestPayload, null, 2))}>
                {copied ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </button>
              <pre>{JSON.stringify(requestPayload, null, 2)}</pre>
            </div>
          </div>
          
          {/* Error Section */}
          {isFailed && job.error && (
            <div className="detail-section error-section">
              <h3><AlertCircle className="w-4 h-4" /> Error Log</h3>
              <div className="error-block">
                <pre>{job.error}</pre>
              </div>
            </div>
          )}
          
          {/* Logs Section */}
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
                  <span className="log-msg">Job completed successfully - {formatDuration(job.duration_seconds)} audio generated</span>
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
            <Trash2 className="w-4 h-4" /> Delete Job
          </button>
        </div>
      </div>
    </div>
  );
};

// Job Row Component
const JobRow = ({ job, onDownload, onDelete, onClick }) => {
  const isDone = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isProcessing = ['queued', 'chunking', 'transcribing', 'merging'].includes(job.status);
  const isStuck = isProcessing && (new Date() - new Date(job.updated_at)) > 120000;
  
  const getStatusColor = () => {
    if (isDone) return 'success';
    if (isFailed) return 'danger';
    if (isStuck) return 'warning';
    return 'processing';
  };
  
  const runTime = getJobRunTime(job);
  const statusColor = getStatusColor();

  return (
    <div className={`job-row ${statusColor}`} onClick={onClick} data-testid={`jobs-table-row-${job.id}`}>
      <div className="job-cell name-cell">
        <div className={`status-dot ${statusColor}`} />
        <div className="job-name-info">
          <span className="job-name" data-testid="job-name-cell">{job.name}</span>
          {isFailed && job.error && <span className="job-error-hint">Click to view error</span>}
        </div>
      </div>
      
      <div className="job-cell">
        <span className="cell-value">{job.text_length?.toLocaleString()}</span>
        <span className="cell-label">chars</span>
      </div>
      
      <div className="job-cell">
        <span className="cell-value">{job.chunk_count}</span>
        <span className="cell-label">chunks</span>
      </div>
      
      <div className="job-cell">
        <span className="cell-value">{isDone && job.duration_seconds ? formatDuration(job.duration_seconds) : '-'}</span>
        <span className="cell-label">audio</span>
      </div>
      
      <div className="job-cell">
        <span className="cell-value">{runTime || '-'}</span>
        <span className="cell-label">process time</span>
      </div>
      
      <div className="job-cell progress-cell">
        <div className="progress-mini">
          <div className={`progress-mini-bar ${statusColor}`} style={{ width: `${job.progress}%` }} />
        </div>
        <span className="progress-text">{job.progress}%</span>
      </div>
      
      <div className="job-cell status-cell">
        <span className={`status-badge ${statusColor}`}>
          {isDone && <CheckCircle2 className="w-3 h-3" />}
          {isFailed && <XCircle className="w-3 h-3" />}
          {isProcessing && !isStuck && <Loader2 className="w-3 h-3 animate-spin" />}
          {isStuck && <AlertCircle className="w-3 h-3" />}
          {isStuck ? 'Stuck' : job.status}
        </span>
      </div>
      
      <div className="job-cell actions-cell" onClick={e => e.stopPropagation()}>
        {isDone && (
          <button className="action-btn primary" onClick={() => onDownload(job)} data-testid="job-download-button">
            <Download className="w-4 h-4" />
          </button>
        )}
        <button className="action-btn ghost" onClick={() => onDelete(job.id)} data-testid="job-delete-button">
          <Trash2 className="w-4 h-4" />
        </button>
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
        toast.success('Job created!');
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
        toast.success('Job removed');
        fetchJobs();
      }
    } catch (error) {
      toast.error('Failed to remove');
    }
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
        {/* Header - Centered */}
        <header className="header">
          <div className="brand-centered">
            <div className="brand-icon">
              <Volume2 className="w-7 h-7" />
            </div>
            <div>
              <h1>Larnyx TTS</h1>
              <span>Powered by ElevenLabs v3</span>
            </div>
          </div>
          <button className="refresh-btn" onClick={fetchJobs}>
            <RefreshCw className="w-5 h-5" />
          </button>
        </header>
        
        {/* Stats Row */}
        <div className="stats-bar">
          <div className="stat-item">
            <div className="stat-icon success"><CheckCircle2 className="w-5 h-5" /></div>
            <div><span className="stat-num">{completedJobs.length}</span><span className="stat-lbl">Completed</span></div>
          </div>
          <div className="stat-item">
            <div className="stat-icon processing"><Activity className="w-5 h-5" /></div>
            <div><span className="stat-num">{processingJobs.length}</span><span className="stat-lbl">Processing</span></div>
          </div>
          <div className="stat-item">
            <div className="stat-icon danger"><XCircle className="w-5 h-5" /></div>
            <div><span className="stat-num">{failedJobs.length}</span><span className="stat-lbl">Failed</span></div>
          </div>
          <div className="stat-item">
            <div className="stat-icon accent"><Clock className="w-5 h-5" /></div>
            <div><span className="stat-num">{formatDuration(totalDuration)}</span><span className="stat-lbl">Total Audio</span></div>
          </div>
          <div className="stat-item">
            <div className="stat-icon muted"><FileText className="w-5 h-5" /></div>
            <div><span className="stat-num">{totalChars > 1000 ? `${(totalChars/1000).toFixed(0)}K` : totalChars}</span><span className="stat-lbl">Characters</span></div>
          </div>
        </div>
        
        {/* Create Job Card */}
        <div className="create-section">
          <div className="glass-card">
            <div className="card-header">
              <Mic className="w-5 h-5" />
              <span>Create New Job</span>
            </div>
            <form onSubmit={handleSubmit} className="create-form">
              <div className="form-row">
                <div className="form-field">
                  <label>Project Name</label>
                  <input
                    type="text"
                    placeholder="e.g., Chapter 1 Narration"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    data-testid="job-name-input"
                  />
                </div>
                <div className="form-field flex-grow">
                  <label>Text Content</label>
                  <input
                    type="text"
                    placeholder="Paste your text here or use the expanded view below..."
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    data-testid="job-text-textarea"
                  />
                </div>
                <button type="submit" className="submit-btn" disabled={!canSubmit} data-testid="create-job-submit-button">
                  {isCreating ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                </button>
              </div>
              <div className="form-meta">
                <span>{charCount.toLocaleString()} chars</span>
                <span>{wordCount.toLocaleString()} words</span>
                {charCount > 100 && <span className="highlight">~{estimatedChunks} chunks</span>}
                {charCount > 0 && charCount < 100 && <span className="warning">Min 100 chars required</span>}
              </div>
            </form>
          </div>
        </div>
        
        {/* Jobs Table */}
        <div className="glass-card jobs-table-card">
          <div className="card-header">
            <Layers className="w-5 h-5" />
            <span>Jobs</span>
            <span className="badge">{jobs.length}</span>
            <span className="header-hint">Click on a job to view details</span>
          </div>
          
          {/* Table Header */}
          <div className="table-header">
            <div className="th">Name</div>
            <div className="th">Size</div>
            <div className="th">Chunks</div>
            <div className="th">Audio</div>
            <div className="th">Time</div>
            <div className="th">Progress</div>
            <div className="th">Status</div>
            <div className="th">Actions</div>
          </div>
          
          <div className="jobs-list">
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
              jobs.map((job) => (
                <JobRow 
                  key={job.id} 
                  job={job} 
                  onDownload={handleDownload} 
                  onDelete={handleDelete}
                  onClick={() => setSelectedJob(job)}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
