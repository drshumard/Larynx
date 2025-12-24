import React, { useState, useEffect, useCallback } from 'react';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import './App.css';
import { Toaster, toast } from 'sonner';
import { Download, Loader2, Clock, FileText, Mic, AlertCircle, RefreshCw, Trash2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Status chip component
const StatusChip = ({ status }) => {
  const statusMap = {
    queued: 'status-queued',
    processing: 'status-processing',
    completed: 'status-completed',
    failed: 'status-failed'
  };
  
  return (
    <span 
      data-testid="job-status-badge" 
      className={`status-chip ${statusMap[status] || statusMap.queued}`}
      aria-label={`Status: ${status}`}
    >
      {status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
      {status === 'completed' && <span className="status-dot completed" />}
      {status === 'failed' && <AlertCircle className="w-3 h-3" />}
      {status === 'queued' && <Clock className="w-3 h-3" />}
      {status}
    </span>
  );
};

// Progress bar component
const ProgressBar = ({ value, processedChunks, totalChunks }) => {
  return (
    <div className="progress-container">
      <div className="progress-bar">
        <div 
          className="progress-fill"
          style={{ width: `${value}%` }}
          data-testid="job-progress-bar"
        />
      </div>
      <span className="progress-label">
        {processedChunks}/{totalChunks} chunks
      </span>
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
    }
  };
  
  return (
    <div className="card form-card">
      <div className="card-header">
        <h2 className="card-title">
          <Mic className="w-5 h-5" />
          Create TTS Job
        </h2>
      </div>
      <form onSubmit={handleSubmit} className="card-content">
        <div className="form-group">
          <label htmlFor="name" className="form-label">Name</label>
          <input
            id="name"
            type="text"
            className="form-input"
            placeholder="Project or voice label"
            value={name}
            onChange={(e) => setName(e.target.value)}
            data-testid="job-name-input"
            maxLength={200}
          />
        </div>
        <div className="form-group">
          <label htmlFor="text" className="form-label">Text</label>
          <textarea
            id="text"
            className="form-textarea"
            placeholder="Paste your long text here (minimum 100 characters)...\n\nThe text will be automatically split into chunks at sentence boundaries for natural speech flow."
            value={text}
            onChange={(e) => setText(e.target.value)}
            data-testid="job-text-textarea"
            rows={12}
          />
          <div className="char-count">
            <span>{charCount.toLocaleString()} characters</span>
            <span className="separator">•</span>
            <span>{wordCount.toLocaleString()} words</span>
            {charCount < 100 && <span className="warning">Minimum 100 characters required</span>}
          </div>
        </div>
        <div className="form-footer">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!canSubmit}
            data-testid="create-job-submit-button"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <FileText className="w-4 h-4" />
                Create TTS Job
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

// Jobs Table component
const JobsTable = ({ jobs, onDownload, onDelete, isLoading }) => {
  if (isLoading && jobs.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <FileText className="w-5 h-5" />
            Jobs
          </h2>
        </div>
        <div className="loading-skeleton">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton-row" />
          ))}
        </div>
      </div>
    );
  }
  
  if (jobs.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <FileText className="w-5 h-5" />
            Jobs
          </h2>
        </div>
        <div className="empty-state" data-testid="jobs-empty-state">
          <Mic className="w-12 h-12" />
          <h3>No jobs yet</h3>
          <p>Create your first TTS job to get started</p>
        </div>
      </div>
    );
  }
  
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
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  return (
    <div className="card table-card">
      <div className="card-header">
        <h2 className="card-title">
          <FileText className="w-5 h-5" />
          Jobs ({jobs.length})
        </h2>
      </div>
      <div className="table-wrapper">
        <table className="jobs-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Duration</th>
              <th>Created</th>
              <th className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              const isDone = job.status === 'completed';
              return (
                <tr key={job.id} data-testid={`jobs-table-row-${job.id}`}>
                  <td data-testid="job-name-cell">
                    <div className="job-name">
                      {job.name}
                      <span className="job-meta">{job.text_length?.toLocaleString()} chars</span>
                    </div>
                  </td>
                  <td>
                    <StatusChip status={job.status} />
                  </td>
                  <td>
                    <ProgressBar 
                      value={job.progress} 
                      processedChunks={job.processed_chunks}
                      totalChunks={job.chunk_count}
                    />
                  </td>
                  <td className="duration-cell">
                    {formatDuration(job.duration_seconds)}
                  </td>
                  <td className="date-cell">
                    {formatDate(job.created_at)}
                  </td>
                  <td className="actions-cell">
                    <div className="action-buttons">
                      {isDone ? (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onDownload(job)}
                          data-testid="job-download-button"
                        >
                          <Download className="w-4 h-4" />
                          Download
                        </button>
                      ) : job.status === 'failed' ? (
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => onDelete(job.id)}
                          data-testid="job-delete-button"
                        >
                          <Trash2 className="w-4 h-4" />
                          Delete
                        </button>
                      ) : (
                        <span className="processing-text">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Processing
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Stats card component
const StatsCard = ({ jobs }) => {
  const completed = jobs.filter(j => j.status === 'completed').length;
  const processing = jobs.filter(j => j.status === 'processing' || j.status === 'queued').length;
  const failed = jobs.filter(j => j.status === 'failed').length;
  
  return (
    <div className="card stats-card">
      <div className="card-header">
        <h2 className="card-title">
          <Clock className="w-5 h-5" />
          Summary
        </h2>
      </div>
      <div className="stats-grid">
        <div className="stat-item">
          <span className="stat-value">{completed}</span>
          <span className="stat-label">Completed</span>
        </div>
        <div className="stat-item">
          <span className="stat-value processing">{processing}</span>
          <span className="stat-label">Processing</span>
        </div>
        <div className="stat-item">
          <span className="stat-value failed">{failed}</span>
          <span className="stat-label">Failed</span>
        </div>
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
    
    // Poll for updates every 2 seconds if there are processing jobs
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
        const newJob = await response.json();
        toast.success('Job created successfully! Processing will begin shortly.');
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
      
      {/* Header */}
      <header className="header">
        <div className="container header-content">
          <div className="logo">
            <Mic className="w-6 h-6" />
            <span>TTS Chunker</span>
          </div>
          <button className="btn btn-ghost" onClick={fetchJobs} title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </header>
      
      {/* Hero */}
      <section className="hero">
        <div className="container">
          <h1>Text to Speech Chunker</h1>
          <p>Process very long texts, see chunk-by-chunk progress, and download MP3s.</p>
        </div>
      </section>
      
      {/* Main content */}
      <main className="main">
        <div className="container">
          <div className="main-grid">
            {/* Form column */}
            <div className="form-column">
              <CreateJobForm onSubmit={handleCreateJob} isLoading={isCreating} />
            </div>
            
            {/* Stats column */}
            <div className="stats-column">
              <StatsCard jobs={jobs} />
            </div>
            
            {/* Table column - full width */}
            <div className="table-column">
              <JobsTable 
                jobs={jobs} 
                onDownload={handleDownload}
                onDelete={handleDelete}
                isLoading={isLoadingJobs}
              />
            </div>
          </div>
        </div>
      </main>
      
      {/* Footer */}
      <footer className="footer">
        <div className="container">
          <p>Powered by ElevenLabs • Text split at sentence boundaries for natural speech</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
