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
  AudioLines,
  Sparkles
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Job Card Component - Each job displayed as a card
const JobCard = ({ job, onDownload, onDelete }) => {
  const isDone = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isProcessing = ['queued', 'chunking', 'transcribing', 'merging'].includes(job.status);
  
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };
  
  const formatDuration = (seconds) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  const getStatusColor = () => {
    switch (job.status) {
      case 'completed': return 'status-completed';
      case 'failed': return 'status-failed';
      case 'queued': return 'status-queued';
      default: return 'status-processing';
    }
  };
  
  const getStatusIcon = () => {
    switch (job.status) {
      case 'completed': return <CheckCircle2 className="w-4 h-4" />;
      case 'failed': return <AlertCircle className="w-4 h-4" />;
      case 'queued': return <Clock className="w-4 h-4" />;
      default: return <Loader2 className="w-4 h-4 animate-spin" />;
    }
  };

  return (
    <div className={`job-card ${isDone ? 'completed' : ''} ${isFailed ? 'failed' : ''}`} data-testid={`jobs-table-row-${job.id}`}>
      {/* Card Header */}
      <div className="job-card-header">
        <div className="job-card-title">
          <div className="job-icon">
            <Volume2 className="w-5 h-5" />
          </div>
          <div className="job-info">
            <h3 data-testid="job-name-cell">{job.name}</h3>
            <span className="job-meta">{job.text_length?.toLocaleString()} characters • {job.chunk_count} chunk{job.chunk_count !== 1 ? 's' : ''}</span>
          </div>
        </div>
        <div className={`status-badge ${getStatusColor()}`} data-testid="job-status-badge">
          {getStatusIcon()}
          <span>{job.status}</span>
        </div>
      </div>
      
      {/* Progress Section */}
      <div className="job-card-progress">
        <div className="progress-header">
          <span className="progress-label">
            {isProcessing ? (job.stage || 'Processing...') : (isDone ? 'Complete' : 'Failed')}
          </span>
          <span className="progress-value">{job.progress}%</span>
        </div>
        <div className="progress-bar-container" data-testid="job-progress-bar">
          <div 
            className={`progress-bar-fill ${isDone ? 'complete' : ''} ${isFailed ? 'failed' : ''}`}
            style={{ width: `${job.progress}%` }}
          />
        </div>
        <div className="progress-details">
          <span>{job.processed_chunks}/{job.chunk_count} chunks processed</span>
          {isDone && <span className="duration">Duration: {formatDuration(job.duration_seconds)}</span>}
        </div>
      </div>
      
      {/* Card Footer */}
      <div className="job-card-footer">
        <span className="job-date">
          <Clock className="w-3.5 h-3.5" />
          {formatDate(job.created_at)}
        </span>
        <div className="job-actions">
          {isDone && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onDownload(job)}
              data-testid="job-download-button"
            >
              <Download className="w-4 h-4" />
              Download MP3
            </button>
          )}
          {isFailed && (
            <button
              className="btn btn-danger btn-sm"
              onClick={() => onDelete(job.id)}
              data-testid="job-delete-button"
            >
              <Trash2 className="w-4 h-4" />
              Remove
            </button>
          )}
          {isProcessing && (
            <span className="processing-indicator">
              <Loader2 className="w-4 h-4 animate-spin" />
              Processing...
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

// Create Job Form component
const CreateJobForm = ({ onSubmit, isLoading }) => {
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  
  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
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
        <div className="form-icon">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h2>Create New TTS Job</h2>
          <p>Transform your text into natural speech</p>
        </div>
      </div>
      <form onSubmit={handleSubmit} className="form-content">
        <div className="form-group">
          <label htmlFor="name">Project Name</label>
          <input
            id="name"
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
          <label htmlFor="text">Text Content</label>
          <textarea
            id="text"
            className="form-textarea"
            placeholder="Paste your long text here...\n\nThe text will be automatically chunked at sentence boundaries for natural speech flow."
            value={text}
            onChange={(e) => setText(e.target.value)}
            data-testid="job-text-textarea"
            rows={10}
          />
          <div className="text-stats">
            <div className="stat-pills">
              <span className="stat-pill">
                <FileText className="w-3.5 h-3.5" />
                {charCount.toLocaleString()} chars
              </span>
              <span className="stat-pill">
                <AudioLines className="w-3.5 h-3.5" />
                {wordCount.toLocaleString()} words
              </span>
            </div>
            {charCount > 0 && charCount < 100 && (
              <span className="min-warning">Min 100 characters required</span>
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
              Creating Job...
            </>
          ) : (
            <>
              <Mic className="w-5 h-5" />
              Generate Speech
              <ChevronRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>
    </div>
  );
};

// Stats Overview Cards
const StatsOverview = ({ jobs }) => {
  const completed = jobs.filter(j => j.status === 'completed').length;
  const processing = jobs.filter(j => ['queued', 'chunking', 'transcribing', 'merging'].includes(j.status)).length;
  const failed = jobs.filter(j => j.status === 'failed').length;
  const totalDuration = jobs
    .filter(j => j.duration_seconds)
    .reduce((acc, j) => acc + j.duration_seconds, 0);
  
  const formatTotalDuration = (seconds) => {
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    const remainingMins = mins % 60;
    return `${hours}h ${remainingMins}m`;
  };
  
  return (
    <div className="stats-grid">
      <div className="stat-card completed">
        <div className="stat-icon">
          <CheckCircle2 className="w-5 h-5" />
        </div>
        <div className="stat-content">
          <span className="stat-value">{completed}</span>
          <span className="stat-label">Completed</span>
        </div>
      </div>
      <div className="stat-card processing">
        <div className="stat-icon">
          <Loader2 className="w-5 h-5" />
        </div>
        <div className="stat-content">
          <span className="stat-value">{processing}</span>
          <span className="stat-label">Processing</span>
        </div>
      </div>
      <div className="stat-card failed">
        <div className="stat-icon">
          <AlertCircle className="w-5 h-5" />
        </div>
        <div className="stat-content">
          <span className="stat-value">{failed}</span>
          <span className="stat-label">Failed</span>
        </div>
      </div>
      <div className="stat-card duration">
        <div className="stat-icon">
          <Clock className="w-5 h-5" />
        </div>
        <div className="stat-content">
          <span className="stat-value">{formatTotalDuration(totalDuration)}</span>
          <span className="stat-label">Total Audio</span>
        </div>
      </div>
    </div>
  );
};

// Jobs Database Section
const JobsDatabase = ({ jobs, onDownload, onDelete, isLoading }) => {
  if (isLoading && jobs.length === 0) {
    return (
      <div className="jobs-section">
        <div className="section-header">
          <h2><FileText className="w-5 h-5" /> Jobs Database</h2>
        </div>
        <div className="jobs-loading">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton-card" />
          ))}
        </div>
      </div>
    );
  }
  
  if (jobs.length === 0) {
    return (
      <div className="jobs-section">
        <div className="section-header">
          <h2><FileText className="w-5 h-5" /> Jobs Database</h2>
        </div>
        <div className="empty-state" data-testid="jobs-empty-state">
          <div className="empty-icon">
            <Mic className="w-12 h-12" />
          </div>
          <h3>No jobs yet</h3>
          <p>Create your first TTS job to get started</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="jobs-section">
      <div className="section-header">
        <h2><FileText className="w-5 h-5" /> Jobs Database</h2>
        <span className="job-count">{jobs.length} job{jobs.length !== 1 ? 's' : ''}</span>
      </div>
      <div className="jobs-grid">
        {jobs.map((job) => (
          <JobCard 
            key={job.id} 
            job={job} 
            onDownload={onDownload}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
};

function App() {
  const [jobs, setJobs] = useState([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  
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
  
  // Initial fetch and polling
  useEffect(() => {
    fetchJobs();
    
    // Poll for updates every 2 seconds
    const interval = setInterval(() => {
      fetchJobs();
    }, 2000);
    
    return () => clearInterval(interval);
  }, [fetchJobs]);
  
  // Create job
  const handleCreateJob = async (jobData) => {
    setIsCreating(true);
    try {
      const response = await fetch(`${API_URL}/api/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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
      console.error('Error creating job:', error);
      toast.error('Failed to create job. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };
  
  // Download job audio
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
        toast.error('Failed to download audio');
      }
    } catch (error) {
      console.error('Error downloading:', error);
      toast.error('Failed to download audio');
    }
  };
  
  // Delete job
  const handleDelete = async (jobId) => {
    try {
      const response = await fetch(`${API_URL}/api/jobs/${jobId}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        toast.success('Job deleted');
        fetchJobs();
      } else {
        toast.error('Failed to delete job');
      }
    } catch (error) {
      console.error('Error deleting job:', error);
      toast.error('Failed to delete job');
    }
  };
  
  return (
    <div className="app">
      <Toaster position="top-right" richColors />
      
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-icon">
              <Mic className="w-6 h-6" />
            </div>
            <span>TTS Chunker</span>
          </div>
        </div>
        <nav className="sidebar-nav">
          <a href="#" className="nav-item active">
            <Sparkles className="w-5 h-5" />
            <span>Dashboard</span>
          </a>
          <a href="#" className="nav-item">
            <FileText className="w-5 h-5" />
            <span>All Jobs</span>
          </a>
        </nav>
        <div className="sidebar-footer">
          <div className="powered-by">
            <span>Powered by</span>
            <strong>ElevenLabs v3</strong>
          </div>
        </div>
      </aside>
      
      {/* Main Content */}
      <main className="main-content">
        {/* Header */}
        <header className="main-header">
          <div className="header-left">
            <span className="greeting">Good {new Date().getHours() < 12 ? 'Morning' : new Date().getHours() < 18 ? 'Afternoon' : 'Evening'}</span>
            <h1>Text to Speech Studio</h1>
          </div>
          <div className="header-right">
            <button className="btn btn-ghost" onClick={fetchJobs} title="Refresh">
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        </header>
        
        {/* Stats Overview */}
        <StatsOverview jobs={jobs} />
        
        {/* Main Grid */}
        <div className="content-grid">
          {/* Left Column - Form */}
          <div className="form-column">
            <CreateJobForm onSubmit={handleCreateJob} isLoading={isCreating} />
          </div>
          
          {/* Right Column - Jobs */}
          <div className="jobs-column">
            <JobsDatabase 
              jobs={jobs} 
              onDownload={handleDownload}
              onDelete={handleDelete}
              isLoading={isLoadingJobs}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
