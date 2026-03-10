/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { 
  Rocket, 
  Upload, 
  FileText, 
  Zap, 
  Play, 
  Search, 
  ChevronRight, 
  LayoutDashboard, 
  Settings, 
  LogOut,
  CheckCircle2,
  Clock,
  MoreVertical,
  ArrowRight,
  User,
  Star,
  Sparkles,
  Copy,
  Check
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import {
  changePassword,
  clearStoredAuthToken,
  fetchCurrentUser,
  fetchVideoJob,
  fetchVideoJobs,
  fetchVideoSourceUrl,
  getStoredAuthToken,
  retryVideoJob,
  signIn,
  signOut,
  signUp,
  updateProfile,
  uploadVideo,
  type AuthUser,
  type VideoJob,
  type VideoJobStatus,
} from './lib/api';

// --- Types ---
type Screen = 'landing' | 'auth' | 'dashboard' | 'analysis' | 'review' | 'history' | 'settings';

interface UserProfile {
  id: string;
  name: string;
  email: string;
  tenantId: string;
  tenantName: string;
}

type LanguageHint = 'auto' | 'en' | 'tl';
type ProcessingStep = 'Uploading' | 'Extracting' | 'Transcribing' | 'Summarizing' | 'Failed';

const statusLabels: Record<VideoJobStatus, string> = {
  queued: 'Queued',
  extracting_audio: 'Extracting',
  transcribing: 'Transcribing',
  analyzing: 'Summarizing',
  completed: 'Completed',
  failed: 'Failed',
};

const statusProgress: Record<VideoJobStatus, number> = {
  queued: 10,
  extracting_audio: 35,
  transcribing: 65,
  analyzing: 90,
  completed: 100,
  failed: 100,
};

const formatDuration = (seconds: number | null | undefined) => {
  if (!seconds || Number.isNaN(seconds)) {
    return '--:--';
  }

  const totalSeconds = Math.max(0, Math.round(seconds));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainingSeconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  }

  return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
};

const formatRelativeTime = (value: string) => {
  const date = new Date(value);
  const diffMs = date.getTime() - Date.now();
  const diffMinutes = Math.round(diffMs / 60000);
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(diffMinutes, 'minute');
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return formatter.format(diffHours, 'hour');
  }

  const diffDays = Math.round(diffHours / 24);
  return formatter.format(diffDays, 'day');
};

const downloadJsonFile = (filename: string, payload: unknown) => {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const getStepFromStatus = (status: VideoJobStatus): ProcessingStep => {
  if (status === 'extracting_audio') {
    return 'Extracting';
  }
  if (status === 'transcribing') {
    return 'Transcribing';
  }
  if (status === 'analyzing' || status === 'completed') {
    return 'Summarizing';
  }
  if (status === 'failed') {
    return 'Failed';
  }
  return 'Uploading';
};

const isJobComplete = (status: VideoJobStatus) => status === 'completed';
const isJobFailed = (status: VideoJobStatus) => status === 'failed';

const mapAuthUserToProfile = (user: AuthUser): UserProfile => ({
  id: user.id,
  name: user.full_name,
  email: user.email,
  tenantId: user.tenant_id,
  tenantName: user.tenant_name,
});

// --- Components ---

const Input = ({ label, type = 'text', placeholder, icon: Icon }: { label: string; type?: string; placeholder: string; icon?: any }) => (
  <div className="space-y-2">
    <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">{label}</label>
    <div className="relative">
      {Icon && <Icon className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />}
      <input 
        type={type} 
        placeholder={placeholder}
        className={`w-full bg-white/5 border border-white/10 rounded-xl py-3 ${Icon ? 'pl-12' : 'px-4'} pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all`}
      />
    </div>
  </div>
);

const Button = ({ 
  children, 
  variant = 'primary', 
  className = '', 
  onClick,
  type = 'button',
  disabled = false,
}: { 
  children: React.ReactNode; 
  variant?: 'primary' | 'secondary' | 'ghost' | 'neon'; 
  className?: string;
  onClick?: () => void;
  type?: 'button' | 'submit';
  disabled?: boolean;
}) => {
  const baseStyles = "px-6 py-3 rounded-full font-medium transition-all duration-300 flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50 disabled:pointer-events-none";
  const variants = {
    primary: "bg-white text-midnight hover:bg-white/90",
    secondary: "bg-white/10 text-white hover:bg-white/20 border border-white/10",
    ghost: "bg-transparent text-white hover:bg-white/5",
    neon: "bg-neon-cyan text-midnight hover:shadow-[0_0_20px_rgba(0,242,255,0.5)] font-bold"
  };

  return (
    <button type={type} className={`${baseStyles} ${variants[variant]} ${className}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
};

const Sidebar = ({ activeTab, onNavigate, user, onLogout }: { activeTab: Screen; onNavigate: (screen: Screen) => void; user: UserProfile | null; onLogout: () => void }) => (
  <aside className="w-64 border-r border-white/10 flex flex-col p-6 h-screen sticky top-0 bg-midnight/50 backdrop-blur-md z-50 print:hidden">
    <div className="flex items-center gap-3 mb-12 cursor-pointer" onClick={() => onNavigate('landing')}>
      <div className="w-10 h-10 bg-gradient-to-br from-neon-cyan to-neon-purple rounded-xl flex items-center justify-center">
        <Rocket className="text-midnight w-6 h-6" />
      </div>
      <span className="text-xl font-bold tracking-tighter">ZENITH AI</span>
    </div>

    <nav className="flex-1 space-y-2">
      <button 
        onClick={() => onNavigate('dashboard')}
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${activeTab === 'dashboard' || activeTab === 'analysis' || activeTab === 'review' ? 'bg-white/10 text-neon-cyan' : 'text-white/60 hover:text-white hover:bg-white/5'}`}
      >
        <LayoutDashboard size={20} />
        Dashboard
      </button>
      <button 
        onClick={() => onNavigate('history')}
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${activeTab === 'history' ? 'bg-white/10 text-neon-cyan' : 'text-white/60 hover:text-white hover:bg-white/5'}`}
      >
        <Clock size={20} />
        History
      </button>
      <button 
        onClick={() => onNavigate('settings')}
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${activeTab === 'settings' ? 'bg-white/10 text-neon-cyan' : 'text-white/60 hover:text-white hover:bg-white/5'}`}
      >
        <Settings size={20} />
        Settings
      </button>
    </nav>

    <div className="mt-auto pt-6 border-t border-white/10">
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="w-8 h-8 rounded-full bg-neon-purple/20 flex items-center justify-center border border-neon-purple/30">
          <User size={16} className="text-neon-purple" />
        </div>
        <div className="flex-1 overflow-hidden">
          <p className="text-sm font-medium truncate">{user?.name || 'User'}</p>
          <p className="text-xs text-white/40 truncate">{user?.tenantName || 'No workspace selected'}</p>
        </div>
        <LogOut 
          size={18} 
          className="text-white/40 hover:text-white cursor-pointer transition-colors" 
          onClick={onLogout}
        />
      </div>
    </div>
  </aside>
);

const DashboardLayout = ({ children, activeTab, onNavigate, user, onLogout }: { children: React.ReactNode; activeTab: Screen; onNavigate: (screen: Screen) => void; user: UserProfile | null; onLogout: () => void }) => (
  <div className="flex h-screen overflow-hidden">
    <Sidebar activeTab={activeTab} onNavigate={onNavigate} user={user} onLogout={onLogout} />
    {children}
  </div>
);

const DemoModal = ({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) => (
  <AnimatePresence>
    {isOpen && (
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-midnight/80 backdrop-blur-sm"
        />
        <motion.div 
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="glass-panel relative z-10 w-full max-w-3xl overflow-hidden p-8"
        >
          <button 
            onClick={onClose}
            className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors z-20"
          >
            <LogOut size={20} className="rotate-180" />
          </button>
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-[0.3em] text-neon-cyan">Platform Flow</p>
              <h3 className="text-3xl font-bold">What happens after you upload a video</h3>
              <p className="text-sm text-white/50">
                The app stores the video, extracts WAV audio with FFmpeg, sends the audio to Whisper, then forwards the transcript to the agent service for summary, action items, and sentiment.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <Upload className="mb-3 text-neon-cyan" size={24} />
                <h4 className="mb-2 font-bold">1. Upload</h4>
                <p className="text-sm text-white/50">Video is saved in the backend and a tenant-scoped processing job is created.</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <FileText className="mb-3 text-neon-cyan" size={24} />
                <h4 className="mb-2 font-bold">2. Transcribe</h4>
                <p className="text-sm text-white/50">FFmpeg extracts audio, then Whisper returns the transcript and detected language.</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <Sparkles className="mb-3 text-neon-cyan" size={24} />
                <h4 className="mb-2 font-bold">3. Analyze</h4>
                <p className="text-sm text-white/50">The agent service uses `gpt-4o` to generate summary, action items, and sentiment.</p>
              </div>
            </div>

            <div className="flex justify-end">
              <Button variant="neon" onClick={onClose}>Close Overview</Button>
            </div>
          </div>
        </motion.div>
      </div>
    )}
  </AnimatePresence>
);

// --- Screens ---

const AuthScreen = ({
  initialMode = 'signin',
  onAuthSuccess,
}: {
  initialMode?: 'signin' | 'signup';
  onAuthSuccess: (user: UserProfile) => void;
}) => {
  const [mode, setMode] = useState(initialMode);
  const [fullName, setFullName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const resetForm = () => {
    setFullName('');
    setTenantName('');
    setEmail('');
    setPassword('');
    setErrorMessage(null);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (mode === 'signup') {
      if (fullName.trim().length < 2) {
        setErrorMessage('Full name must be at least 2 characters.');
        return;
      }
      if (tenantName.trim().length < 2) {
        setErrorMessage('Workspace name must be at least 2 characters.');
        return;
      }
    }

    if (!email.includes('@')) {
      setErrorMessage('Enter a valid email address.');
      return;
    }
    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters.');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = mode === 'signup'
        ? await signUp({
            full_name: fullName.trim(),
            tenant_name: tenantName.trim(),
            email: email.trim().toLowerCase(),
            password,
          })
        : await signIn({
            email: email.trim().toLowerCase(),
            password,
          });

      resetForm();
      onAuthSuccess(mapAuthUserToProfile(response.user));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Authentication failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] cosmic-gradient opacity-20 pointer-events-none" />
      
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-panel w-full max-w-md p-10 relative z-10"
      >
        <div className="flex flex-col items-center mb-10">
          <div className="w-12 h-12 bg-gradient-to-br from-neon-cyan to-neon-purple rounded-xl flex items-center justify-center mb-4">
            <Rocket className="text-midnight w-7 h-7" />
          </div>
          <h2 className="text-3xl font-bold tracking-tight">
            {mode === 'signin' ? 'Welcome Back' : 'Create Account'}
          </h2>
          <p className="text-white/40 text-sm mt-2">
            {mode === 'signin' ? 'Enter your credentials to access your workspace' : 'Create a workspace and sign in'}
          </p>
        </div>

        <form className="space-y-6" onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <>
              <div className="space-y-2">
                <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Full Name</label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                  <input
                    type="text"
                    value={fullName}
                    onChange={(event) => setFullName(event.target.value)}
                    placeholder="Maria Santos"
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Workspace Name</label>
                <div className="relative">
                  <LayoutDashboard className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                  <input
                    type="text"
                    value={tenantName}
                    onChange={(event) => setTenantName(event.target.value)}
                    placeholder="Acme Product Team"
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                  />
                </div>
              </div>
            </>
          )}

          <div className="space-y-2">
            <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Email Address</label>
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@company.com"
                className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Password</label>
            <div className="relative">
              <Settings className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Password with 8+ characters"
                className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
              />
            </div>
          </div>

          {errorMessage && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {errorMessage}
            </div>
          )}
          
          <Button variant="neon" className="w-full py-4 text-lg" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Processing...' : mode === 'signin' ? 'Sign In' : 'Create Account'}
          </Button>
        </form>

        <div className="mt-8 text-center">
          <p className="text-white/40 text-sm">
            {mode === 'signin' ? "Don't have an account?" : "Already have an account?"}{' '}
            <button 
              onClick={() => {
                setMode(mode === 'signin' ? 'signup' : 'signin');
                resetForm();
              }}
              className="text-neon-cyan hover:underline font-medium"
            >
              {mode === 'signin' ? 'Sign Up' : 'Sign In'}
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
};

const HistoryScreen = ({
  jobs,
  isLoading,
  onOpenJob,
}: {
  jobs: VideoJob[];
  isLoading: boolean;
  onOpenJob: (job: VideoJob) => void;
}) => {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | VideoJobStatus>('all');
  const filteredJobs = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return jobs.filter((job) => {
      const matchesQuery = !normalizedQuery || job.original_filename.toLowerCase().includes(normalizedQuery);
      const matchesStatus = statusFilter === 'all' || job.status === statusFilter;
      return matchesQuery && matchesStatus;
    });
  }, [jobs, query, statusFilter]);

  const handleExportAll = () => {
    downloadJsonFile(
      `video-jobs-${new Date().toISOString().slice(0, 10)}.json`,
      filteredJobs.map((job) => ({
        id: job.id,
        filename: job.original_filename,
        status: job.status,
        duration_seconds: job.duration_seconds,
        created_at: job.created_at,
        completed_at: job.completed_at,
        sentiment: job.sentiment,
        action_items: job.action_items,
        summary: job.summary,
        error_message: job.error_message,
      })),
    );
  };

  return (
    <div className="flex-1 p-10 overflow-y-auto">
      <header className="mb-10">
        <h1 className="text-4xl font-bold mb-2">Video History</h1>
        <p className="text-white/50">Review and manage your past video analyses</p>
      </header>

      <div className="glass-panel overflow-hidden">
        <div className="p-6 border-b border-white/10 flex items-center justify-between bg-white/5">
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={16} />
            <input 
              type="text" 
              placeholder="Search history..." 
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-10 pr-4 text-sm focus:outline-none focus:border-neon-cyan/50 transition-colors"
            />
          </div>
          <div className="flex gap-2">
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as 'all' | VideoJobStatus)}
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-white focus:outline-none focus:border-neon-cyan/50"
            >
              <option value="all" className="bg-midnight text-white">All Statuses</option>
              <option value="queued" className="bg-midnight text-white">Queued</option>
              <option value="extracting_audio" className="bg-midnight text-white">Extracting</option>
              <option value="transcribing" className="bg-midnight text-white">Transcribing</option>
              <option value="analyzing" className="bg-midnight text-white">Summarizing</option>
              <option value="completed" className="bg-midnight text-white">Completed</option>
              <option value="failed" className="bg-midnight text-white">Failed</option>
            </select>
            <Button variant="secondary" className="px-4 py-2 text-xs" onClick={handleExportAll} disabled={filteredJobs.length === 0}>Export JSON</Button>
          </div>
        </div>
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/10 bg-white/5">
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Name</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Status</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Duration</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {isLoading ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : filteredJobs.length > 0 ? (
              filteredJobs.map((job) => (
                <tr 
                  key={job.id} 
                  className="hover:bg-white/5 transition-colors cursor-pointer group"
                  onClick={() => onOpenJob(job)}
                >
                  <td className="px-6 py-4 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center">
                      <Play size={16} className="text-white/60" />
                    </div>
                    <span className="font-medium">{job.original_filename}</span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                      isJobComplete(job.status)
                        ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                        : isJobFailed(job.status)
                          ? 'bg-red-500/10 text-red-500 border-red-500/20'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}>
                      {isJobComplete(job.status) ? <CheckCircle2 size={12} /> : <Zap size={12} />}
                      {statusLabels[job.status]}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-white/60 text-sm">{formatDuration(job.duration_seconds)}</td>
                  <td className="px-6 py-4 text-white/60 text-sm">{formatRelativeTime(job.created_at)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-6 py-10 text-center text-sm text-white/40" colSpan={4}>
                  No video jobs found yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const SettingsScreen = ({ user, onUpdateUser }: { user: UserProfile | null; onUpdateUser: (updates: Partial<UserProfile>) => void }) => {
  const [name, setName] = useState(user?.name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [tenantName, setTenantName] = useState(user?.tenantName || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [securityMessage, setSecurityMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [securityError, setSecurityError] = useState<string | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingPassword, setIsSavingPassword] = useState(false);

  useEffect(() => {
    setName(user?.name || '');
    setEmail(user?.email || '');
    setTenantName(user?.tenantName || '');
  }, [user]);

  const handleSaveProfile = async () => {
    setProfileError(null);
    setProfileMessage(null);

    if (name.trim().length < 2) {
      setProfileError('Full name must be at least 2 characters.');
      return;
    }
    if (!email.includes('@')) {
      setProfileError('Enter a valid email address.');
      return;
    }
    if (tenantName.trim().length < 2) {
      setProfileError('Workspace name must be at least 2 characters.');
      return;
    }

    setIsSavingProfile(true);
    try {
      const updatedUser = await updateProfile({
        full_name: name.trim(),
        email: email.trim().toLowerCase(),
        tenant_name: tenantName.trim(),
      });
      onUpdateUser(mapAuthUserToProfile(updatedUser));
      setProfileMessage('Profile updated');
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : 'Unable to update profile');
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    setSecurityError(null);
    setSecurityMessage(null);

    if (currentPassword.length < 8) {
      setSecurityError('Enter your current password.');
      return;
    }
    if (newPassword.length < 8) {
      setSecurityError('New password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setSecurityError('New password and confirmation must match.');
      return;
    }

    setIsSavingPassword(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setSecurityMessage('Password updated');
    } catch (error) {
      setSecurityError(error instanceof Error ? error.message : 'Unable to update password');
    } finally {
      setIsSavingPassword(false);
    }
  };

  return (
    <div className="flex-1 p-10 overflow-y-auto">
      <header className="mb-10">
        <h1 className="text-4xl font-bold mb-2">Account Settings</h1>
        <p className="text-white/50">Manage your profile, workspace name, and password.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <section className="glass-panel p-8">
            <h3 className="text-xl font-bold mb-6">Profile Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Full Name</label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                  <input 
                    type="text" 
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Your full name"
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Email Address</label>
                <div className="relative">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                  <input 
                    type="email" 
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="your@company.com"
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                  />
                </div>
              </div>
            </div>
            <div className="mt-6 space-y-2">
              <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Workspace Name</label>
              <div className="relative">
                <LayoutDashboard className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                <input 
                  type="text" 
                  value={tenantName}
                  onChange={(event) => setTenantName(event.target.value)}
                  placeholder="Your workspace name"
                  className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                />
              </div>
            </div>
            <div className="mt-8 flex items-center gap-4 flex-wrap">
              <Button variant="neon" onClick={handleSaveProfile} disabled={isSavingProfile}>{isSavingProfile ? 'Saving...' : 'Save Changes'}</Button>
              {profileMessage && <span className="text-emerald-500 text-sm font-medium">{profileMessage}</span>}
              {profileError && <span className="text-red-400 text-sm font-medium">{profileError}</span>}
            </div>
          </section>

          <section className="glass-panel p-8">
            <h3 className="text-xl font-bold mb-6">Security</h3>
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Current Password</label>
                <div className="relative">
                  <Settings className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    placeholder="Enter current password"
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">New Password</label>
                  <div className="relative">
                    <Settings className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      placeholder="Enter new password"
                      className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-white/40 uppercase tracking-widest ml-1">Confirm New Password</label>
                  <div className="relative">
                    <Settings className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      placeholder="Confirm new password"
                      className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-8 flex items-center gap-4 flex-wrap">
              <Button variant="secondary" onClick={handleChangePassword} disabled={isSavingPassword}>{isSavingPassword ? 'Updating...' : 'Update Password'}</Button>
              {securityMessage && <span className="text-emerald-500 text-sm font-medium">{securityMessage}</span>}
              {securityError && <span className="text-red-400 text-sm font-medium">{securityError}</span>}
            </div>
          </section>
        </div>

        <div className="space-y-8">
          <section className="glass-panel p-8 border-white/10">
            <h3 className="text-xl font-bold mb-4">Workspace Scope</h3>
            <p className="text-sm text-white/40 mb-4">Your workspace name is the tenant identity for this project. Uploaded videos and AI analysis results are isolated by workspace.</p>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white/70">
              Workspace: <span className="text-white font-medium">{tenantName || 'Not available'}</span>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
const SkeletonRow = () => (
  <tr className="animate-pulse">
    <td className="px-6 py-4 flex items-center gap-3">
      <div className="w-10 h-10 rounded-lg bg-white/5" />
      <div className="h-4 w-32 bg-white/5 rounded" />
    </td>
    <td className="px-6 py-4">
      <div className="h-6 w-20 bg-white/5 rounded-full" />
    </td>
    <td className="px-6 py-4">
      <div className="h-4 w-12 bg-white/5 rounded" />
    </td>
    <td className="px-6 py-4">
      <div className="h-4 w-24 bg-white/5 rounded" />
    </td>
  </tr>
);

const Dashboard = ({
  jobs,
  isLoading,
  isUploading,
  uploadError,
  onUpload,
  onViewAll,
  onOpenJob,
}: {
  jobs: VideoJob[];
  isLoading: boolean;
  isUploading: boolean;
  uploadError: string | null;
  onUpload: (file: File, languageHint: LanguageHint) => void;
  onViewAll: () => void;
  onOpenJob: (job: VideoJob) => void;
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [languageHint, setLanguageHint] = useState<LanguageHint>('auto');
  const recentJobs = jobs.slice(0, 5);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onUpload(file, languageHint);
    }
    event.target.value = '';
  };

  const triggerUpload = () => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  return (
    <div className="flex-1 p-10 overflow-y-auto">
      <input 
        type="file" 
        ref={fileInputRef} 
        className="hidden" 
        accept="video/*" 
        onChange={handleFileChange}
      />
      <header className="mb-10 flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold mb-2">Welcome back</h1>
          <p className="text-white/50">Ready to analyze your next video?</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={languageHint}
            onChange={(event) => setLanguageHint(event.target.value as LanguageHint)}
            className="rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:border-neon-cyan/50"
          >
            <option value="auto" className="bg-midnight text-white">Auto Detect</option>
            <option value="en" className="bg-midnight text-white">English</option>
            <option value="tl" className="bg-midnight text-white">Tagalog</option>
          </select>
          <Button variant="neon" onClick={triggerUpload} className="px-8 py-4 shadow-lg shadow-neon-cyan/20" disabled={isUploading}>
            <Upload size={20} />
            {isUploading ? 'Uploading...' : 'Upload Video'}
          </Button>
        </div>
      </header>

      {uploadError && (
        <div className="mb-6 rounded-2xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-200">
          {uploadError}
        </div>
      )}

      {/* Upload Zone */}
      <motion.div 
        whileHover={{ scale: 1.01 }}
        className="glass-panel p-16 mb-12 flex flex-col items-center justify-center border-dashed border-2 border-white/20 hover:border-neon-cyan/50 transition-all cursor-pointer group"
        onClick={triggerUpload}
      >
        <div className="w-20 h-20 rounded-full bg-neon-cyan/10 flex items-center justify-center mb-6 group-hover:bg-neon-cyan/20 transition-colors">
          <Upload className="text-neon-cyan" size={40} />
        </div>
        <h2 className="text-2xl font-bold mb-2">Upload New Video</h2>
        <p className="text-white/40 mb-8">Whisper transcription runs remotely and supports English plus Tagalog code-switching.</p>
        <Button variant="secondary" className="group-hover:bg-white group-hover:text-midnight" disabled={isUploading}>
          Select Files
        </Button>
      </motion.div>

      {/* Recent Uploads */}
      <section>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold">Recent Uploads</h3>
          <button 
            onClick={onViewAll}
            className="text-sm text-neon-cyan hover:underline flex items-center gap-1"
          >
            View All <ChevronRight size={16} />
          </button>
        </div>
        <div className="glass-panel overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-white/10 bg-white/5">
                <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Name</th>
                <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Status</th>
                <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Duration</th>
                <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-white/40">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isLoading ? (
                <>
                  <SkeletonRow />
                  <SkeletonRow />
                  <SkeletonRow />
                </>
              ) : (
                recentJobs.length > 0 ? recentJobs.map((job) => (
                  <tr 
                    key={job.id} 
                    className="hover:bg-white/5 transition-colors cursor-pointer group"
                    onClick={() => onOpenJob(job)}
                  >
                    <td className="px-6 py-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center">
                        <Play size={16} className="text-white/60" />
                      </div>
                      <span className="font-medium">{job.original_filename}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                        isJobComplete(job.status)
                          ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                          : isJobFailed(job.status)
                            ? 'bg-red-500/10 text-red-500 border-red-500/20'
                            : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}>
                        {isJobComplete(job.status) ? <CheckCircle2 size={12} /> : <Clock size={12} />}
                        {statusLabels[job.status]}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-white/60 text-sm">{formatDuration(job.duration_seconds)}</td>
                    <td className="px-6 py-4 text-white/60 text-sm">{formatRelativeTime(job.created_at)}</td>
                  </tr>
                )) : (
                  <tr>
                    <td className="px-6 py-10 text-center text-sm text-white/40" colSpan={4}>
                      Upload a video to start the first analysis job.
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

const AnalysisScreen = ({
  jobId,
  onComplete,
  onRetry,
  onAuthError,
  onOpenHistory,
}: {
  jobId: string | null;
  onComplete: (job: VideoJob) => void;
  onRetry: (jobId: string) => Promise<void>;
  onAuthError: (message: string) => void;
  onOpenHistory: () => void;
}) => {
  const [job, setJob] = useState<VideoJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return undefined;
    }

    let isCancelled = false;
    let timeoutId: number | undefined;

    const pollJob = async () => {
      try {
        const latestJob = await fetchVideoJob(jobId);
        if (isCancelled) {
          return;
        }

        setJob(latestJob);
        setErrorMessage(null);

        if (latestJob.status === 'completed') {
          onComplete(latestJob);
          return;
        }

        if (latestJob.status === 'failed') {
          return;
        }

        timeoutId = window.setTimeout(pollJob, 2500);
      } catch (error) {
        if (isCancelled) {
          return;
        }

        const message = error instanceof Error ? error.message : 'Unable to load job status';
        onAuthError(message);
        setErrorMessage(message);
        timeoutId = window.setTimeout(pollJob, 4000);
      }
    };

    void pollJob();

    return () => {
      isCancelled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [jobId, onAuthError, onComplete]);

  const handleRetry = async () => {
    if (!jobId) {
      return;
    }

    setIsRetrying(true);
    setErrorMessage(null);
    try {
      await onRetry(jobId);
      setJob((currentJob) => currentJob ? {
        ...currentJob,
        status: 'queued',
        error_message: null,
        summary: null,
        sentiment: null,
        action_items: [],
        transcript: null,
        completed_at: null,
      } : currentJob);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to retry job';
      onAuthError(message);
      setErrorMessage(message);
    } finally {
      setIsRetrying(false);
    }
  };

  const currentStatus = job?.status ?? 'queued';
  const step = getStepFromStatus(currentStatus);
  const progress = statusProgress[currentStatus];
  const isFailed = currentStatus === 'failed';
  const headline = !jobId
    ? 'No active job'
    : isFailed
      ? 'Analysis failed'
      : step === 'Uploading'
        ? 'Uploading Video...'
        : 'Analyzing Content...';
  const description = !jobId
    ? 'Upload a video from the dashboard to start processing.'
    : isFailed
    ? job?.error_message || 'The pipeline stopped before results were generated.'
    : errorMessage || 'Your upload is being processed through extraction, transcription, and agent analysis.';

  return (
    <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 cosmic-gradient opacity-40" />
      
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 w-full max-w-2xl px-6 text-center"
      >
        <div className="mb-12 relative inline-block">
          <div className="absolute inset-0 bg-neon-cyan/20 blur-3xl rounded-full animate-pulse" />
          <div className="w-24 h-24 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center relative z-10 mx-auto">
            <Zap className="text-neon-cyan animate-bounce" size={48} />
          </div>
        </div>

        <h2 className="text-4xl font-bold mb-4">{headline}</h2>
        <p className="text-white/50 mb-12">
          {description}
        </p>

        <div className="space-y-6">
          <div className="flex justify-between text-sm font-medium mb-2">
            <span className={step === 'Uploading' ? 'text-neon-cyan' : 'text-white/30'}>Uploading</span>
            <span className={step === 'Extracting' ? 'text-neon-cyan' : 'text-white/30'}>Extracting</span>
            <span className={step === 'Transcribing' ? 'text-neon-cyan' : 'text-white/30'}>Transcribing</span>
            <span className={step === 'Summarizing' ? 'text-neon-cyan' : 'text-white/30'}>Summarizing</span>
          </div>
          
          <div className="h-4 w-full bg-white/5 rounded-full overflow-hidden border border-white/10 p-1">
            <motion.div 
              className="h-full bg-gradient-to-r from-neon-cyan to-neon-purple rounded-full shadow-[0_0_15px_rgba(0,242,255,0.5)]"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ ease: "linear" }}
            />
          </div>
          
          <p className="text-neon-cyan font-mono text-lg">{progress}% Complete</p>
          {job && (
            <div className="space-y-2 text-sm text-white/50">
              <p>{job.original_filename}</p>
              <p>Status: {statusLabels[job.status]}</p>
              {job.detected_language && <p>Detected language: {job.detected_language}</p>}
            </div>
          )}
          {isFailed && (
            <div className="flex items-center justify-center gap-4">
              <Button variant="neon" onClick={handleRetry} disabled={isRetrying}>
                {isRetrying ? 'Retrying...' : 'Retry Processing'}
              </Button>
              <Button variant="secondary" onClick={onOpenHistory}>Open History</Button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
};

const ReviewScreen = ({ job }: { job: VideoJob | null }) => {
  const [activeTab, setActiveTab] = useState<'summary' | 'transcript'>('summary');
  const [copied, setCopied] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [videoSourceUrl, setVideoSourceUrl] = useState<string | null>(null);
  const [videoSourceError, setVideoSourceError] = useState<string | null>(null);
  const [isVideoLoading, setIsVideoLoading] = useState(false);

  const handleExportPDF = () => {
    window.print();
  };

  const actionItems = job?.action_items ?? [];
  const summaryText = job?.summary ?? 'No summary generated yet.';
  const allTranscriptEntries = useMemo(() => {
    const transcript = job?.transcript ?? '';
    return transcript
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean);
  }, [job?.transcript]);

  const transcriptEntries = useMemo(() => {
    if (!searchTerm.trim()) {
      return allTranscriptEntries;
    }

    const normalizedSearch = searchTerm.toLowerCase();
    return allTranscriptEntries.filter((line) => line.toLowerCase().includes(normalizedSearch));
  }, [allTranscriptEntries, searchTerm]);

  const handleCopy = () => {
    navigator.clipboard.writeText(summaryText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    if (!job?.id) {
      setVideoSourceUrl(null);
      setVideoSourceError(null);
      return undefined;
    }

    let isCancelled = false;
    let currentUrl: string | null = null;

    const loadVideoSource = async () => {
      setIsVideoLoading(true);
      setVideoSourceError(null);
      try {
        const sourceUrl = await fetchVideoSourceUrl(job.id);
        if (isCancelled) {
          URL.revokeObjectURL(sourceUrl);
          return;
        }

        currentUrl = sourceUrl;
        setVideoSourceUrl(sourceUrl);
      } catch (error) {
        if (!isCancelled) {
          setVideoSourceError(error instanceof Error ? error.message : 'Unable to load video preview');
          setVideoSourceUrl(null);
        }
      } finally {
        if (!isCancelled) {
          setIsVideoLoading(false);
        }
      }
    };

    void loadVideoSource();

    return () => {
      isCancelled = true;
      if (currentUrl) {
        URL.revokeObjectURL(currentUrl);
      }
    };
  }, [job?.id]);

  return (
    <div className="flex-1 p-10 overflow-hidden flex flex-col">
      <header className="mb-8 flex justify-between items-center">
        <div>
          <div className="flex items-center gap-2 text-xs text-white/40 uppercase tracking-widest mb-1">
            <span>Videos</span>
            <ChevronRight size={12} />
            <span className="text-white/60">{job?.original_filename ?? 'No analysis selected'}</span>
          </div>
          <h1 className="text-3xl font-bold">{job?.original_filename ?? 'Analysis Review'}</h1>
        </div>
        <div className="flex gap-3 print:hidden">
          <Button variant="secondary" className="px-5 py-2 text-sm" onClick={handleExportPDF}>Export PDF</Button>
        </div>
      </header>

      <div className="flex-1 flex gap-8 overflow-hidden print:block print:overflow-visible">
        {/* Video Player Left */}
        <div className="flex-[1.5] flex flex-col gap-6 overflow-hidden print:hidden">
          <div className="aspect-video glass-panel overflow-hidden relative group">
            {videoSourceUrl ? (
              <video
                src={videoSourceUrl}
                controls
                preload="metadata"
                className="w-full h-full bg-black object-contain"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                <div className="text-center space-y-3 px-6">
                  <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full border border-white/20 bg-white/10 backdrop-blur-md">
                    <Play className="text-white fill-white ml-1" size={32} />
                  </div>
                  <p className="text-sm text-white/60">
                    {isVideoLoading ? 'Loading uploaded video...' : (videoSourceError ?? 'Video preview is unavailable')}
                  </p>
                </div>
              </div>
            )}
            {/* Controls Overlay */}
            {!videoSourceUrl && (
              <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-midnight to-transparent">
                <div className="text-sm text-white/50">
                  Uploaded source: {job?.original_filename ?? 'Unavailable'}
                </div>
              </div>
            )}
          </div>

          <div className="glass-panel p-6">
            <h3 className="font-bold mb-4 flex items-center gap-2">
              <Zap size={18} className="text-neon-cyan" />
              Quick Stats
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                <p className="text-xs text-white/40 mb-1">Transcript Lines</p>
                <p className="text-lg font-bold">{allTranscriptEntries.length}</p>
              </div>
              <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                <p className="text-xs text-white/40 mb-1">Sentiment</p>
                <p className="text-lg font-bold text-emerald-500">{job?.sentiment ?? 'Pending'}</p>
              </div>
              <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                <p className="text-xs text-white/40 mb-1">Action Items</p>
                <p className="text-lg font-bold text-neon-purple">{actionItems.length}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Analysis Right */}
        <div className="flex-1 glass-panel flex flex-col overflow-hidden print:border-none print:bg-transparent print:p-0 print:overflow-visible">
          <div className="flex border-b border-white/10 print:hidden">
            <button 
              onClick={() => setActiveTab('summary')}
              className={`flex-1 py-4 text-sm font-bold transition-colors relative ${activeTab === 'summary' ? 'text-neon-cyan' : 'text-white/40 hover:text-white'}`}
            >
              AI SUMMARY
              {activeTab === 'summary' && <motion.div layoutId="tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-neon-cyan" />}
            </button>
            <button 
              onClick={() => setActiveTab('transcript')}
              className={`flex-1 py-4 text-sm font-bold transition-colors relative ${activeTab === 'transcript' ? 'text-neon-cyan' : 'text-white/40 hover:text-white'}`}
            >
              FULL TRANSCRIPT
              {activeTab === 'transcript' && <motion.div layoutId="tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-neon-cyan" />}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            <AnimatePresence mode="wait">
              {activeTab === 'summary' ? (
                <motion.div 
                  key="summary"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  className="space-y-8"
                >
                  <div className="flex justify-between items-start gap-4">
                    <section className="flex-1">
                      <h4 className="text-xs font-bold text-white/40 uppercase tracking-widest mb-4">Executive Summary</h4>
                      <p className="text-white/80 leading-relaxed">
                        {summaryText}
                      </p>
                    </section>
                    <button 
                      onClick={handleCopy}
                      className="shrink-0 p-2.5 rounded-xl bg-white/5 border border-white/10 text-white/60 hover:text-neon-cyan hover:border-neon-cyan/50 transition-all flex items-center gap-2 text-xs font-bold group"
                    >
                      {copied ? (
                        <>
                          <Check size={14} className="text-emerald-500" />
                          <span className="text-emerald-500">COPIED</span>
                        </>
                      ) : (
                        <>
                          <Copy size={14} className="group-hover:scale-110 transition-transform" />
                          <span>COPY</span>
                        </>
                      )}
                    </button>
                  </div>

                  <section>
                    <h4 className="text-xs font-bold text-white/40 uppercase tracking-widest mb-4">Sentiment</h4>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-white/80">
                      {job?.sentiment ?? 'Sentiment analysis is still pending.'}
                    </div>
                  </section>

                  <section>
                    <h4 className="text-xs font-bold text-white/40 uppercase tracking-widest mb-4">Action Items</h4>
                    <div className="space-y-3">
                      {actionItems.length > 0 ? actionItems.map((item, i) => (
                        <div key={i} className="p-3 rounded-lg bg-white/5 border border-white/5 flex items-center gap-3">
                          <div className="w-5 h-5 rounded border border-white/20 flex items-center justify-center">
                            <CheckCircle2 size={14} className="text-white/20" />
                          </div>
                          <span className="text-sm">{item}</span>
                        </div>
                      )) : (
                        <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white/50">
                          No action items were extracted from this transcript.
                        </div>
                      )}
                    </div>
                  </section>
                </motion.div>
              ) : (
                <motion.div 
                  key="transcript"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  className="space-y-6"
                >
                  <div className="relative mb-6">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={16} />
                    <input 
                      type="text" 
                      placeholder="Search transcript..." 
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-10 pr-4 text-sm focus:outline-none focus:border-neon-cyan/50 transition-colors"
                    />
                  </div>

                  <div className="space-y-6">
                    {transcriptEntries.length > 0 ? transcriptEntries.map((entry, i) => (
                      <div key={i} className="group cursor-pointer">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono text-neon-cyan">Line {i + 1}</span>
                          <span className="text-xs font-bold text-white/40 uppercase tracking-wider">Transcript</span>
                        </div>
                        <p className="text-sm text-white/70 leading-relaxed group-hover:text-white transition-colors">
                          {entry}
                        </p>
                      </div>
                    )) : (
                      <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white/50">
                        No transcript content matches your search.
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Main App ---

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('landing');
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin');
  const [isDemoOpen, setIsDemoOpen] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthInitializing, setIsAuthInitializing] = useState(true);
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedJob, setSelectedJob] = useState<VideoJob | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const handleUnauthorized = useCallback((message: string) => {
    if (['Authentication required', 'Invalid session', 'Session expired'].includes(message)) {
      clearStoredAuthToken();
      setUser(null);
      setCurrentScreen('auth');
    }
  }, []);

  const loadJobs = useCallback(async () => {
    if (!user) {
      setJobs([]);
      setJobsLoading(false);
      return;
    }

    setJobsLoading(true);
    try {
      const jobList = await fetchVideoJobs();
      setJobs(jobList);
      setJobsError(null);
      setSelectedJob((currentSelectedJob) => {
        if (!currentSelectedJob) {
          return currentSelectedJob;
        }

        const refreshedJob = jobList.find((job) => job.id === currentSelectedJob.id);
        return refreshedJob ? { ...currentSelectedJob, ...refreshedJob } : currentSelectedJob;
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load video jobs';
      handleUnauthorized(message);
      setJobsError(message);
    } finally {
      setJobsLoading(false);
    }
  }, [handleUnauthorized, user]);

  useEffect(() => {
    const bootstrapAuth = async () => {
      if (!getStoredAuthToken()) {
        setIsAuthInitializing(false);
        return;
      }

      try {
        const currentUser = await fetchCurrentUser();
        setUser(mapAuthUserToProfile(currentUser));
        setCurrentScreen('dashboard');
      } catch {
        clearStoredAuthToken();
      } finally {
        setIsAuthInitializing(false);
      }
    };

    void bootstrapAuth();
  }, []);

  useEffect(() => {
    if (user) {
      void loadJobs();
    } else {
      setJobs([]);
      setJobsLoading(false);
    }
  }, [loadJobs, user]);

  const handleAuthSuccess = (authenticatedUser: UserProfile) => {
    setUser(authenticatedUser);
    setCurrentScreen('dashboard');
  };

  const handleLogout = () => {
    void signOut().catch(() => undefined);
    setUser(null);
    setJobs([]);
    setSelectedJob(null);
    setActiveJobId(null);
    setCurrentScreen('landing');
  };

  const handleUpdateUser = (updates: Partial<UserProfile>) => {
    setUser(prev => prev ? { ...prev, ...updates } : null);
  };

  const handleUpload = useCallback(async (file: File, languageHint: LanguageHint) => {
    if (!user) {
      setJobsError('Sign in before uploading a video.');
      setCurrentScreen('auth');
      return;
    }

    setIsUploading(true);
    setJobsError(null);

    try {
      const response = await uploadVideo(file, languageHint);
      setActiveJobId(response.id);
      setSelectedJob(null);
      setCurrentScreen('analysis');
      void loadJobs();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Upload failed';
      handleUnauthorized(message);
      setJobsError(message);
    } finally {
      setIsUploading(false);
    }
  }, [handleUnauthorized, loadJobs, user]);

  const handleOpenJob = useCallback(async (job: VideoJob) => {
    setActiveJobId(job.id);
    try {
      const detailedJob = await fetchVideoJob(job.id);
      setSelectedJob(detailedJob);
      setCurrentScreen(detailedJob.status === 'completed' ? 'review' : 'analysis');
    } catch (error) {
      if (error instanceof Error) {
        handleUnauthorized(error.message);
      }
      setSelectedJob(job);
      setCurrentScreen(job.status === 'completed' ? 'review' : 'analysis');
    }
  }, [handleUnauthorized]);

  const handleAnalysisComplete = useCallback(async (job: VideoJob) => {
    setSelectedJob(job);
    setActiveJobId(job.id);
    await loadJobs();
    setCurrentScreen('review');
  }, [loadJobs]);

  const handleRetryJob = useCallback(async (jobId: string) => {
    await retryVideoJob(jobId);
    const refreshedJob = await fetchVideoJob(jobId);
    setSelectedJob(refreshedJob);
    setActiveJobId(refreshedJob.id);
    await loadJobs();
    setCurrentScreen('analysis');
  }, [loadJobs]);

  if (isAuthInitializing) {
    return (
      <div className="min-h-screen bg-midnight text-white flex items-center justify-center">
        <div className="glass-panel px-8 py-6 text-sm text-white/60">Loading workspace...</div>
      </div>
    );
  }

  const renderScreen = () => {
    switch (currentScreen) {
      case 'landing':
        return <LandingPage onStart={(mode) => { setAuthMode(mode); setCurrentScreen('auth'); }} onWatchDemo={() => setIsDemoOpen(true)} />;
      case 'auth':
        return <AuthScreen initialMode={authMode} onAuthSuccess={handleAuthSuccess} />;
      case 'dashboard':
        return (
          <DashboardLayout activeTab="dashboard" onNavigate={setCurrentScreen} user={user} onLogout={handleLogout}>
            <Dashboard 
              jobs={jobs}
              isLoading={jobsLoading}
              isUploading={isUploading}
              uploadError={jobsError}
              onUpload={handleUpload}
              onViewAll={() => setCurrentScreen('history')}
              onOpenJob={handleOpenJob}
            />
          </DashboardLayout>
        );
      case 'history':
        return (
          <DashboardLayout activeTab="history" onNavigate={setCurrentScreen} user={user} onLogout={handleLogout}>
            <HistoryScreen 
              jobs={jobs}
              isLoading={jobsLoading}
              onOpenJob={handleOpenJob}
            />
          </DashboardLayout>
        );
      case 'settings':
        return (
          <DashboardLayout activeTab="settings" onNavigate={setCurrentScreen} user={user} onLogout={handleLogout}>
            <SettingsScreen user={user} onUpdateUser={handleUpdateUser} />
          </DashboardLayout>
        );
      case 'analysis':
        return (
          <DashboardLayout activeTab="dashboard" onNavigate={setCurrentScreen} user={user} onLogout={handleLogout}>
            <AnalysisScreen
              jobId={activeJobId}
              onComplete={handleAnalysisComplete}
              onRetry={handleRetryJob}
              onAuthError={handleUnauthorized}
              onOpenHistory={() => {
                void loadJobs();
                setCurrentScreen('history');
              }}
            />
          </DashboardLayout>
        );
      case 'review':
        return (
          <DashboardLayout activeTab="dashboard" onNavigate={setCurrentScreen} user={user} onLogout={handleLogout}>
            <ReviewScreen job={selectedJob} />
          </DashboardLayout>
        );
      default:
        return <LandingPage onStart={(mode) => { setAuthMode(mode); setCurrentScreen('auth'); }} onWatchDemo={() => setIsDemoOpen(true)} />;
    }
  };

  return (
    <div className="min-h-screen bg-midnight text-white selection:bg-neon-cyan/30">
      <AnimatePresence mode="wait">
        <motion.div
          key={currentScreen}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="h-full"
        >
          {renderScreen()}
        </motion.div>
      </AnimatePresence>
      <DemoModal isOpen={isDemoOpen} onClose={() => setIsDemoOpen(false)} />
    </div>
  );
}

