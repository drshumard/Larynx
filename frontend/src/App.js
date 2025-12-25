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
  Sparkles,
  XCircle,
  Activity,
  Timer,
  Layers,
  Play,
  Zap,
  BarChart3,
  AudioWaveform
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

// Job Row Component
const JobRow = ({ job, onDownload, onDelete }) => {
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
    <div className={`job-row ${statusColor}`} data-testid={`jobs-table-row-${job.id}`}>
      <div className="job-row-left">
        <div className={`job-status-indicator ${statusColor}`}>
          {isDone && <CheckCircle2 className="w-4 h-4" />}
          {isFailed && <XCircle className="w-4 h-4" />}
          {isStuck && <AlertCircle className="w-4 h-4" />}
          {isProcessing && !isStuck && <Loader2 className="w-4 h-4 animate-spin" />}
        </div>
        <div className="job-details">
          <span className="job-name" data-testid="job-name-cell">{job.name}</span>
          <span className="job-meta">
            {job.text_length?.toLocaleString()} chars • {job.chunk_count} chunks
            {isDone && job.duration_seconds && ` • ${formatDuration(job.duration_seconds)} audio`}
            {runTime && <span className="run-time"> • {runTime} to process</span>}
          </span>
        </div>
      </div>
      
      <div className="job-row-center">
        <div className="progress-wrapper">
          <div className="progress-track">
            <div className={`progress-bar ${statusColor}`} style={{ width: `${job.progress}%` }} data-testid="job-progress-bar" />
          </div>
          <span className="progress-text">{job.progress}%</span>
        </div>
        <span className="job-stage">{isProcessing ? job.stage : (isDone ? 'Complete' : 'Failed')}</span>
      </div>
      
      <div className="job-row-right">
        <span className="job-date">{formatDate(job.created_at)}</span>
        <div className="job-actions">
          {isDone && (
            <button className="action-btn primary" onClick={() => onDownload(job)} data-testid="job-download-button">
              <Download className="w-4 h-4" />
            </button>
          )}
          {(isFailed || isStuck || isProcessing) && (
            <button className="action-btn danger" onClick={() => onDelete(job.id)} data-testid="job-delete-button">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
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
      
      <div className="dashboard">
        {/* Header */}
        <header className="header">
          <div className="brand">
            <div className="brand-icon">
              <Volume2 className="w-6 h-6" />
            </div>
            <div>
              <h1>TTS Chunker</h1>
              <span>ElevenLabs v3</span>
            </div>
          </div>
          <button className="refresh-btn" onClick={fetchJobs}>
            <RefreshCw className="w-5 h-5" />
          </button>
        </header>
        
        {/* Main Grid */}
        <div className="main-grid">
          {/* Left Column */}
          <div className="left-col">
            {/* Stats Row */}
            <div className="stats-row">
              <div className="stat-card">
                <div className="stat-icon success"><CheckCircle2 className="w-5 h-5" /></div>
                <div className="stat-info">
                  <span className="stat-value">{completedJobs.length}</span>
                  <span className="stat-label">Completed</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon processing"><Activity className="w-5 h-5" /></div>
                <div className="stat-info">
                  <span className="stat-value">{processingJobs.length}</span>
                  <span className="stat-label">Processing</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon danger"><XCircle className="w-5 h-5" /></div>
                <div className="stat-info">
                  <span className="stat-value">{failedJobs.length}</span>
                  <span className="stat-label">Failed</span>
                </div>
              </div>
            </div>
            
            {/* Analytics Card */}
            <div className="glass-card analytics-card">
              <div className="card-header">
                <BarChart3 className="w-5 h-5" />
                <span>Analytics</span>
              </div>
              <div className="analytics-grid">
                <div className="analytics-item">
                  <span className="analytics-value">{formatDuration(totalDuration)}</span>
                  <span className="analytics-label">Total Audio</span>
                  <div className="mini-bar"><div className="mini-bar-fill orange" style={{width: '80%'}} /></div>
                </div>
                <div className="analytics-item">
                  <span className="analytics-value">{totalChars > 1000 ? `${(totalChars/1000).toFixed(0)}K` : totalChars}</span>
                  <span className="analytics-label">Characters</span>
                  <div className="mini-bar"><div className="mini-bar-fill teal" style={{width: '65%'}} /></div>
                </div>
                <div className="analytics-item">
                  <span className="analytics-value">{jobs.length}</span>
                  <span className="analytics-label">Total Jobs</span>
                  <div className="mini-bar"><div className="mini-bar-fill purple" style={{width: '50%'}} /></div>
                </div>
                <div className="analytics-item">
                  <span className="analytics-value">{completedJobs.length > 0 ? Math.round(completedJobs.reduce((a,j) => a + j.chunk_count, 0) / completedJobs.length) : 0}</span>
                  <span className="analytics-label">Avg Chunks</span>
                  <div className="mini-bar"><div className="mini-bar-fill pink" style={{width: '40%'}} /></div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Right Column - Create Job */}
          <div className="right-col">
            <div className="glass-card create-card">
              <div className="card-header">
                <Mic className="w-5 h-5" />
                <span>Create New Job</span>
              </div>
              <form onSubmit={handleSubmit} className="create-form">
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
                <div className="form-field">
                  <label>Text Content</label>
                  <textarea
                    placeholder="Paste your text here..."
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    data-testid="job-text-textarea"
                  />
                  <div className="text-meta">
                    <span>{charCount.toLocaleString()} chars</span>
                    <span>{wordCount.toLocaleString()} words</span>
                    {charCount > 100 && <span className="highlight">~{estimatedChunks} chunks</span>}
                  </div>
                </div>
                <button type="submit" className="submit-btn" disabled={!canSubmit} data-testid="create-job-submit-button">
                  {isCreating ? (
                    <><Loader2 className="w-5 h-5 animate-spin" /> Creating...</>
                  ) : (
                    <><Play className="w-5 h-5" /> Generate Speech</>
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
        
        {/* Jobs Section - Full Width */}
        <div className="glass-card jobs-card">
          <div className="card-header">
            <Layers className="w-5 h-5" />
            <span>Jobs</span>
            <span className="badge">{jobs.length}</span>
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
                <JobRow key={job.id} job={job} onDownload={handleDownload} onDelete={handleDelete} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
