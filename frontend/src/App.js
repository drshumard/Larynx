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
  Info,
  MoreHorizontal,
  StopCircle
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Format duration helper
const formatDuration = (seconds) => {
  if (!seconds) return '--:--';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) {
    return `${hrs}h ${mins}m`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

// Format date helper
const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// Stats Card Component
const StatsCard = ({ icon: Icon, value, label, trend, color = 'default' }) => (
  <div className={`stats-card ${color}`}>
    <div className="stats-card-header">
      <div className="stats-icon">
        <Icon className="w-5 h-5" />
      </div>
      {trend && (
        <span className={`trend ${trend > 0 ? 'positive' : 'negative'}`}>
          <TrendingUp className="w-3 h-3" />
          {Math.abs(trend)}%
        </span>
      )}
    </div>
    <div className="stats-value">{value}</div>
    <div className="stats-label">{label}</div>
  </div>
);

// Progress Ring Component
const ProgressRing = ({ progress, size = 60, strokeWidth = 6 }) => {
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

// Job Card Component
const JobCard = ({ job, onDownload, onDelete, onCancel }) => {
  const isDone = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isProcessing = ['queued', 'chunking', 'transcribing', 'merging'].includes(job.status);
  const isStuck = isProcessing && (new Date() - new Date(job.updated_at)) > 120000; // 2 min no update = stuck
  
  const getStatusInfo = () => {
    if (isDone) return { label: 'Completed', color: 'success' };
    if (isFailed) return { label: 'Failed', color: 'danger' };
    if (isStuck) return { label: 'Stuck', color: 'warning' };
    return { label: job.status, color: 'processing' };
  };
  
  const status = getStatusInfo();

  return (
    <div className={`job-card ${status.color}`} data-testid={`jobs-table-row-${job.id}`}>
      <div className="job-card-main">
        {/* Left: Progress Ring */}
        <div className="job-progress-section">
          <ProgressRing progress={job.progress} />
        </div>
        
        {/* Middle: Job Info */}
        <div className="job-info-section">
          <div className="job-header">
            <h3 className="job-name" data-testid="job-name-cell">{job.name}</h3>
            <span className={`status-badge ${status.color}`} data-testid="job-status-badge">
              {isDone && <CheckCircle2 className="w-3 h-3" />}
              {isFailed && <AlertCircle className="w-3 h-3" />}
              {isProcessing && !isStuck && <Loader2 className="w-3 h-3 animate-spin" />}
              {isStuck && <AlertCircle className="w-3 h-3" />}
              {status.label}
            </span>
          </div>
          
          <div className="job-meta-row">
            <span className="meta-item">
              <FileText className="w-3.5 h-3.5" />
              {job.text_length?.toLocaleString()} chars
            </span>
            <span className="meta-item">
              <Layers className="w-3.5 h-3.5" />
              {job.processed_chunks}/{job.chunk_count} chunks
            </span>
            {isDone && job.duration_seconds && (
              <span className="meta-item">
                <Timer className="w-3.5 h-3.5" />
                {formatDuration(job.duration_seconds)}
              </span>
            )}
          </div>
          
          {/* Progress Bar */}
          <div className="job-progress-bar" data-testid="job-progress-bar">
            <div 
              className={`progress-fill ${status.color}`}
              style={{ width: `${job.progress}%` }}
            />
          </div>
          
          <div className="job-stage">
            {isProcessing ? (job.stage || 'Processing...') : (isDone ? 'Complete' : job.error ? 'Error occurred' : 'Failed')}
          </div>
        </div>
        
        {/* Right: Actions */}
        <div className="job-actions-section">
          {isDone && (
            <button
              className="btn btn-primary"
              onClick={() => onDownload(job)}
              data-testid="job-download-button"
            >
              <Download className="w-4 h-4" />
              Download
            </button>
          )}
          {(isFailed || isStuck) && (
            <button
              className="btn btn-danger"
              onClick={() => onDelete(job.id)}
              data-testid="job-delete-button"
            >
              <Trash2 className="w-4 h-4" />
              Remove
            </button>
          )}
          {isProcessing && !isStuck && (
            <button
              className="btn btn-secondary"
              onClick={() => onCancel(job.id)}
            >
              <StopCircle className="w-4 h-4" />
              Cancel
            </button>
          )}
          <span className="job-date">
            <Clock className="w-3 h-3" />
            {formatDate(job.created_at)}
          </span>
        </div>
      </div>
      
      {/* Error details if failed */}
      {isFailed && job.error && (
        <div className="job-error">
          <AlertCircle className="w-4 h-4" />
          <span>{job.error.includes('max_character_limit') ? 'Chunk size exceeded API limit' : 'Processing error'}</span>
        </div>
      )}
    </div>
  );
};

// Create Job Form
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
    <div className="form-card">
      <div className="form-card-header">
        <div className="form-title">
          <Mic className="w-5 h-5" />
          <span>New TTS Job</span>
        </div>
        <div className="form-subtitle">Convert text to natural speech</div>
      </div>
      
      <form onSubmit={handleSubmit} className="form-content">
        <div className="form-group">
          <label>Project Name</label>
          <input
            type="text"
            className="form-input"
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
            className="form-textarea"
            placeholder="Paste your text here...&#10;&#10;Text will be chunked at sentence boundaries for natural speech."
            value={text}
            onChange={(e) => setText(e.target.value)}
            data-testid="job-text-textarea"
            rows={8}
          />
          
          <div className="text-stats">
            <div className="stat-pills">
              <span className="stat-pill">
                {charCount.toLocaleString()} characters
              </span>
              <span className="stat-pill">
                {wordCount.toLocaleString()} words
              </span>
              {charCount > 100 && (
                <span className="stat-pill highlight">
                  ~{estimatedChunks} chunk{estimatedChunks !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            {charCount > 0 && charCount < 100 && (
              <span className="warning-text">Min 100 characters</span>
            )}
          </div>
        </div>
        
        <button
          type="submit"
          className="btn btn-primary btn-lg full-width"
          disabled={!canSubmit}
          data-testid="create-job-submit-button"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Creating...
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5" />
              Generate Speech
              <ArrowRight className="w-4 h-4" />
            </>
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
  
  // Stats calculations
  const completedJobs = jobs.filter(j => j.status === 'completed');
  const processingJobs = jobs.filter(j => ['queued', 'chunking', 'transcribing', 'merging'].includes(j.status));
  const failedJobs = jobs.filter(j => j.status === 'failed');
  const totalDuration = completedJobs.reduce((acc, j) => acc + (j.duration_seconds || 0), 0);
  const totalChars = jobs.reduce((acc, j) => acc + (j.text_length || 0), 0);
  
  // Fetch jobs
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
  
  // Create job
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
  
  // Download
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
      } else {
        toast.error('Failed to download');
      }
    } catch (error) {
      toast.error('Failed to download');
    }
  };
  
  // Delete
  const handleDelete = async (jobId) => {
    try {
      const response = await fetch(`${API_URL}/api/jobs/${jobId}`, { method: 'DELETE' });
      if (response.ok) {
        toast.success('Job deleted');
        fetchJobs();
      } else {
        toast.error('Failed to delete');
      }
    } catch (error) {
      toast.error('Failed to delete');
    }
  };
  
  // Cancel (same as delete for now)
  const handleCancel = async (jobId) => {
    if (window.confirm('Cancel this job? This cannot be undone.')) {
      handleDelete(jobId);
    }
  };
  
  return (
    <div className="app">
      <Toaster position="top-right" richColors />
      
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <div className="logo-icon">
              <Volume2 className="w-6 h-6" />
            </div>
            <div className="logo-text">
              <span className="logo-title">TTS Chunker</span>
              <span className="logo-subtitle">Powered by ElevenLabs v3</span>
            </div>
          </div>
        </div>
        <div className="header-right">
          <button className="btn btn-icon" onClick={fetchJobs} title="Refresh">
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="main">
        {/* Stats Row */}
        <div className="stats-row">
          <StatsCard 
            icon={CheckCircle2} 
            value={completedJobs.length} 
            label="Completed" 
            color="success"
          />
          <StatsCard 
            icon={Activity} 
            value={processingJobs.length} 
            label="Processing" 
            color="processing"
          />
          <StatsCard 
            icon={XCircle} 
            value={failedJobs.length} 
            label="Failed" 
            color="danger"
          />
          <StatsCard 
            icon={Timer} 
            value={formatDuration(totalDuration)} 
            label="Total Audio" 
            color="accent"
          />
          <StatsCard 
            icon={FileText} 
            value={totalChars > 1000000 ? `${(totalChars/1000000).toFixed(1)}M` : totalChars > 1000 ? `${(totalChars/1000).toFixed(0)}K` : totalChars} 
            label="Characters" 
            color="default"
          />
        </div>
        
        {/* Content Grid */}
        <div className="content-grid">
          {/* Left: Form */}
          <div className="form-column">
            <CreateJobForm onSubmit={handleCreateJob} isLoading={isCreating} />
          </div>
          
          {/* Right: Jobs */}
          <div className="jobs-column">
            <div className="jobs-card">
              <div className="jobs-header">
                <div className="jobs-title">
                  <Layers className="w-5 h-5" />
                  <span>Jobs</span>
                  <span className="job-count">{jobs.length}</span>
                </div>
                <button className="see-details">
                  See All <ArrowRight className="w-4 h-4" />
                </button>
              </div>
              
              <div className="jobs-list">
                {isLoadingJobs && jobs.length === 0 ? (
                  <div className="loading-state">
                    <Loader2 className="w-8 h-8 animate-spin" />
                    <span>Loading jobs...</span>
                  </div>
                ) : jobs.length === 0 ? (
                  <div className="empty-state" data-testid="jobs-empty-state">
                    <div className="empty-icon">
                      <Mic className="w-10 h-10" />
                    </div>
                    <h3>No jobs yet</h3>
                    <p>Create your first TTS job to get started</p>
                  </div>
                ) : (
                  jobs.map((job) => (
                    <JobCard 
                      key={job.id} 
                      job={job} 
                      onDownload={handleDownload}
                      onDelete={handleDelete}
                      onCancel={handleCancel}
                    />
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
