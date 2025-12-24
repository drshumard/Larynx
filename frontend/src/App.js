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
  ChevronRight,
  Volume2,
  Sparkles,
  XCircle,
  TrendingUp,
  Activity,
  Timer,
  Layers,
  ArrowRight,
  Play,
  Zap,
  BarChart3,
  AudioWaveform
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Helpers
const formatDuration = (seconds) => {
  if (!seconds) return '--:--';
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

// Metric Card Component
const MetricCard = ({ icon: Icon, value, label, subtext, color = 'default', large = false }) => (
  <div className={`metric-card ${color} ${large ? 'large' : ''}`}>
    <div className="metric-icon">
      <Icon className="w-6 h-6" />
    </div>
    <div className="metric-content">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      {subtext && <div className="metric-subtext">{subtext}</div>}
    </div>
  </div>
);

// Analytics Card Component
const AnalyticsCard = ({ jobs }) => {
  const completed = jobs.filter(j => j.status === 'completed');
  const totalChars = completed.reduce((acc, j) => acc + (j.text_length || 0), 0);
  const totalDuration = completed.reduce((acc, j) => acc + (j.duration_seconds || 0), 0);
  const avgChunks = completed.length > 0 
    ? Math.round(completed.reduce((acc, j) => acc + j.chunk_count, 0) / completed.length) 
    : 0;
  
  return (
    <div className="analytics-card">
      <div className="analytics-header">
        <BarChart3 className="w-5 h-5" />
        <span>Analytics Overview</span>
      </div>
      <div className="analytics-grid">
        <div className="analytics-item">
          <div className="analytics-value">{completed.length}</div>
          <div className="analytics-label">Jobs Completed</div>
          <div className="analytics-bar">
            <div className="analytics-bar-fill" style={{ width: '100%' }} />
          </div>
        </div>
        <div className="analytics-item">
          <div className="analytics-value">{formatDuration(totalDuration)}</div>
          <div className="analytics-label">Total Audio</div>
          <div className="analytics-bar">
            <div className="analytics-bar-fill orange" style={{ width: '75%' }} />
          </div>
        </div>
        <div className="analytics-item">
          <div className="analytics-value">{totalChars > 1000 ? `${(totalChars/1000).toFixed(0)}K` : totalChars}</div>
          <div className="analytics-label">Characters</div>
          <div className="analytics-bar">
            <div className="analytics-bar-fill pink" style={{ width: '60%' }} />
          </div>
        </div>
        <div className="analytics-item">
          <div className="analytics-value">{avgChunks}</div>
          <div className="analytics-label">Avg Chunks</div>
          <div className="analytics-bar">
            <div className="analytics-bar-fill purple" style={{ width: '45%' }} />
          </div>
        </div>
      </div>
    </div>
  );
};

// Progress Ring
const ProgressRing = ({ progress, size = 72, strokeWidth = 6 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;
  
  return (
    <svg width={size} height={size} className="progress-ring">
      <circle
        className="progress-ring-bg"
        strokeWidth={strokeWidth}
        fill="transparent"
        r={radius}
        cx={size / 2}
        cy={size / 2}
      />
      <circle
        className="progress-ring-fill"
        strokeWidth={strokeWidth}
        fill="transparent"
        r={radius}
        cx={size / 2}
        cy={size / 2}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
      />
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dy="0.35em"
        className="progress-ring-text"
      >
        {progress}%
      </text>
    </svg>
  );
};

// Job Card
const JobCard = ({ job, onDownload, onDelete }) => {
  const isDone = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isProcessing = ['queued', 'chunking', 'transcribing', 'merging'].includes(job.status);
  const isStuck = isProcessing && (new Date() - new Date(job.updated_at)) > 120000;
  
  const getStatusInfo = () => {
    if (isDone) return { label: 'Completed', color: 'success', icon: CheckCircle2 };
    if (isFailed) return { label: 'Failed', color: 'danger', icon: XCircle };
    if (isStuck) return { label: 'Stuck', color: 'warning', icon: AlertCircle };
    return { label: job.status, color: 'processing', icon: Activity };
  };
  
  const status = getStatusInfo();
  const StatusIcon = status.icon;
  const runTime = getJobRunTime(job);

  return (
    <div className={`job-card ${status.color}`} data-testid={`jobs-table-row-${job.id}`}>
      {/* Progress Section */}
      <div className="job-progress">
        <ProgressRing progress={job.progress} />
      </div>
      
      {/* Info Section */}
      <div className="job-info">
        <div className="job-header">
          <h3 className="job-name" data-testid="job-name-cell">{job.name}</h3>
          <span className={`status-badge ${status.color}`} data-testid="job-status-badge">
            {isProcessing && !isStuck ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <StatusIcon className="w-3.5 h-3.5" />
            )}
            {status.label}
          </span>
        </div>
        
        <div className="job-meta">
          <span><FileText className="w-4 h-4" /> {job.text_length?.toLocaleString()} chars</span>
          <span><Layers className="w-4 h-4" /> {job.processed_chunks}/{job.chunk_count} chunks</span>
          {isDone && job.duration_seconds && (
            <span><AudioWaveform className="w-4 h-4" /> {formatDuration(job.duration_seconds)} audio</span>
          )}
          {runTime && (
            <span className="run-time"><Zap className="w-4 h-4" /> {runTime} to process</span>
          )}
        </div>
        
        <div className="job-progress-bar" data-testid="job-progress-bar">
          <div className={`progress-fill ${status.color}`} style={{ width: `${job.progress}%` }} />
        </div>
        
        <div className="job-stage">
          {isProcessing ? (job.stage || 'Processing...') : (isDone ? 'Complete' : 'Error')}
        </div>
      </div>
      
      {/* Actions Section */}
      <div className="job-actions">
        {isDone && (
          <button className="btn btn-primary" onClick={() => onDownload(job)} data-testid="job-download-button">
            <Download className="w-4 h-4" />
            Download
          </button>
        )}
        {(isFailed || isStuck || isProcessing) && (
          <button className="btn btn-ghost-danger" onClick={() => onDelete(job.id)} data-testid="job-delete-button">
            <Trash2 className="w-4 h-4" />
          </button>
        )}
        <div className="job-timestamp">
          <Clock className="w-3.5 h-3.5" />
          {formatDate(job.created_at)}
        </div>
      </div>
    </div>
  );
};

// Create Form
const CreateJobForm = ({ onSubmit, isLoading }) => {
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  
  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const estimatedChunks = Math.ceil(charCount / 4500);
  const canSubmit = name.trim() && text.trim().length >= 100 && !isLoading;
  
  const handleSubmit = (e) => {
    e.preventDefault();
    if (canSubmit) {
      onSubmit({ name: name.trim(), text: text.trim() });
      setName('');
      setText('');
    }
  };
  
  return (
    <div className="create-card">
      <div className="create-header">
        <div className="create-icon">
          <Mic className="w-7 h-7" />
        </div>
        <div>
          <h2>Create New Job</h2>
          <p>Convert text to natural speech</p>
        </div>
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
            maxLength={200}
          />
        </div>
        
        <div className="form-group">
          <label>Text Content</label>
          <textarea
            placeholder="Paste your text here...&#10;&#10;Text will be chunked at sentence boundaries."
            value={text}
            onChange={(e) => setText(e.target.value)}
            data-testid="job-text-textarea"
            rows={6}
          />
          
          <div className="text-info">
            <div className="info-pills">
              <span>{charCount.toLocaleString()} chars</span>
              <span>{wordCount.toLocaleString()} words</span>
              {charCount > 100 && <span className="highlight">~{estimatedChunks} chunks</span>}
            </div>
            {charCount > 0 && charCount < 100 && (
              <span className="warning">Min 100 characters</span>
            )}
          </div>
        </div>
        
        <button type="submit" className="btn btn-primary btn-large" disabled={!canSubmit} data-testid="create-job-submit-button">
          {isLoading ? (
            <><Loader2 className="w-5 h-5 animate-spin" /> Creating...</>
          ) : (
            <><Play className="w-5 h-5" /> Generate Speech<ArrowRight className="w-4 h-4" /></>
          )}
        </button>
      </form>
    </div>
  );
};

// Main App
function App() {
  const [jobs, setJobs] = useState([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  
  const completedJobs = jobs.filter(j => j.status === 'completed');
  const processingJobs = jobs.filter(j => ['queued', 'chunking', 'transcribing', 'merging'].includes(j.status));
  const failedJobs = jobs.filter(j => j.status === 'failed');
  const totalDuration = completedJobs.reduce((acc, j) => acc + (j.duration_seconds || 0), 0);
  
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
  
  const handleCreateJob = async (jobData) => {
    setIsCreating(true);
    try {
      const response = await fetch(`${API_URL}/api/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jobData),
      });
      if (response.ok) {
        toast.success('Job created! Processing will begin shortly.');
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
      
      {/* Header */}
      <header className="header">
        <div className="brand">
          <div className="brand-icon">
            <Volume2 className="w-7 h-7" />
          </div>
          <div className="brand-text">
            <span className="brand-name">TTS Chunker</span>
            <span className="brand-sub">ElevenLabs v3</span>
          </div>
        </div>
        <button className="refresh-btn" onClick={fetchJobs}>
          <RefreshCw className="w-5 h-5" />
        </button>
      </header>
      
      {/* Main */}
      <main className="main">
        {/* Top Row - Metrics */}
        <div className="metrics-row">
          <MetricCard 
            icon={CheckCircle2} 
            value={completedJobs.length} 
            label="Completed" 
            color="success"
            large
          />
          <MetricCard 
            icon={Activity} 
            value={processingJobs.length} 
            label="Processing" 
            color="processing"
          />
          <MetricCard 
            icon={XCircle} 
            value={failedJobs.length} 
            label="Failed" 
            color="danger"
          />
          <MetricCard 
            icon={Timer} 
            value={formatDuration(totalDuration)} 
            label="Total Audio" 
            color="accent"
            large
          />
        </div>
        
        {/* Content Row */}
        <div className="content-row">
          {/* Left Column */}
          <div className="left-column">
            <CreateJobForm onSubmit={handleCreateJob} isLoading={isCreating} />
            <AnalyticsCard jobs={jobs} />
          </div>
          
          {/* Right Column - Jobs */}
          <div className="right-column">
            <div className="jobs-card">
              <div className="jobs-header">
                <div className="jobs-title">
                  <Layers className="w-5 h-5" />
                  <span>Jobs</span>
                  <span className="jobs-count">{jobs.length}</span>
                </div>
                <span className="see-all">See all <ChevronRight className="w-4 h-4" /></span>
              </div>
              
              <div className="jobs-list">
                {isLoadingJobs && jobs.length === 0 ? (
                  <div className="loading-state">
                    <Loader2 className="w-10 h-10 animate-spin" />
                    <span>Loading jobs...</span>
                  </div>
                ) : jobs.length === 0 ? (
                  <div className="empty-state" data-testid="jobs-empty-state">
                    <div className="empty-icon"><Mic className="w-12 h-12" /></div>
                    <h3>No jobs yet</h3>
                    <p>Create your first TTS job</p>
                  </div>
                ) : (
                  jobs.map((job) => (
                    <JobCard key={job.id} job={job} onDownload={handleDownload} onDelete={handleDelete} />
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
