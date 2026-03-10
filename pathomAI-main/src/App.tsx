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
  fetchVideoJob,
  fetchVideoJobs,
  uploadVideo,
  type VideoJob,
  type VideoJobStatus,
} from './lib/api';

// --- Types ---
type Screen = 'landing' | 'auth' | 'dashboard' | 'analysis' | 'review' | 'history' | 'settings';

interface UserProfile {
  name: string;
  email: string;
  isPro: boolean;
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
          <p className="text-xs text-white/40 truncate">{user?.isPro ? 'Pro Member' : 'Free Plan'}</p>
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
          className="glass-panel w-full max-w-4xl aspect-video relative z-10 overflow-hidden"
        >
          <button 
            onClick={onClose}
            className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors z-20"
          >
            <LogOut size={20} className="rotate-180" />
          </button>
          <div className="w-full h-full bg-black flex items-center justify-center">
            <div className="text-center space-y-4">
              <Play size={64} className="text-neon-cyan mx-auto animate-pulse" />
              <p className="text-white/40 font-mono tracking-widest">ZENITH_DEMO_REEL.MP4</p>
            </div>
          </div>
        </motion.div>
      </div>
    )}
  </AnimatePresence>
);

// --- Screens ---

const AuthScreen = ({ initialMode = 'signin', onAuthSuccess }: { initialMode?: 'signin' | 'signup', onAuthSuccess: () => void }) => {
  const [mode, setMode] = useState(initialMode);

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
            {mode === 'signin' ? 'Enter your credentials to access your account' : 'Create your account to start'}
          </p>
        </div>

        <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); onAuthSuccess(); }}>
          {mode === 'signup' && (
            <Input label="Full Name" placeholder="Neil Armstrong" icon={User} />
          )}
          <Input label="Email Address" type="email" placeholder="commander@zenith.ai" icon={Search} />
          <Input label="Password" type="password" placeholder="••••••••" icon={Settings} />
          
          <Button variant="neon" className="w-full py-4 text-lg" type="submit">
            {mode === 'signin' ? 'Sign In' : 'Create Account'}
          </Button>
        </form>

        <div className="mt-8 text-center">
          <p className="text-white/40 text-sm">
            {mode === 'signin' ? "Don't have an account?" : "Already have an account?"}{' '}
            <button 
              onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
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
  const filteredJobs = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return jobs;
    }

    return jobs.filter((job) => job.original_filename.toLowerCase().includes(normalizedQuery));
  }, [jobs, query]);

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
            <Button variant="secondary" className="px-4 py-2 text-xs">Filter</Button>
            <Button variant="secondary" className="px-4 py-2 text-xs">Export All</Button>
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
  const [isSaved, setIsSaved] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const handleSave = () => {
    onUpdateUser({ name, email });
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  return (
    <div className="flex-1 p-10 overflow-y-auto">
      <header className="mb-10">
        <h1 className="text-4xl font-bold mb-2">Account Settings</h1>
        <p className="text-white/50">Manage your account and preferences</p>
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
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Neil Armstrong"
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
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="commander@zenith.ai"
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 transition-all"
                  />
                </div>
              </div>
            </div>
            <div className="mt-8 flex items-center gap-4">
              <Button variant="neon" onClick={handleSave}>Save Changes</Button>
              <AnimatePresence>
                {isSaved && (
                  <motion.span 
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    className="text-emerald-500 text-sm font-medium flex items-center gap-2"
                  >
                    <CheckCircle2 size={16} /> Changes saved successfully
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
          </section>

          <section className="glass-panel p-8">
            <h3 className="text-xl font-bold mb-6">Security</h3>
            <div className="space-y-6">
              <Input label="Current Password" type="password" placeholder="••••••••" icon={Settings} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Input label="New Password" type="password" placeholder="••••••••" icon={Settings} />
                <Input label="Confirm New Password" type="password" placeholder="••••••••" icon={Settings} />
              </div>
            </div>
            <Button variant="secondary" className="mt-8">Update Password</Button>
          </section>
        </div>

        <div className="space-y-8">
          <section className="glass-panel p-8 border-red-500/20">
            <h3 className="text-xl font-bold mb-4 text-red-500">Delete Account</h3>
            <p className="text-sm text-white/40 mb-6">Once you delete your account, there is no going back. Please be certain.</p>
            <Button 
              variant="ghost" 
              className="w-full text-red-500 hover:bg-red-500/10 border border-red-500/20"
              onClick={() => setIsDeleteModalOpen(true)}
            >
              Delete Account
            </Button>
          </section>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {isDeleteModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsDeleteModalOpen(false)}
              className="absolute inset-0 bg-midnight/80 backdrop-blur-sm"
            />
            <motion.div 
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="glass-panel w-full max-w-md p-8 relative z-10"
            >
              <h3 className="text-2xl font-bold mb-4 text-red-500">Are you absolutely sure?</h3>
              <p className="text-white/60 mb-8">
                This action cannot be undone. This will permanently delete your account
                and remove your data from our servers.
              </p>
              <div className="flex gap-4">
                <Button variant="secondary" className="flex-1" onClick={() => setIsDeleteModalOpen(false)}>Cancel</Button>
                <Button variant="ghost" className="flex-1 bg-red-500 hover:bg-red-600 text-white border-none" onClick={() => window.location.reload()}>
                  Delete
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

const LandingPage = ({ onStart, onWatchDemo }: { onStart: (mode: 'signin' | 'signup') => void; onWatchDemo: () => void }) => (
  <div className="min-h-screen flex flex-col">
    {/* Navigation */}
    <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto w-full">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-gradient-to-br from-neon-cyan to-neon-purple rounded-lg flex items-center justify-center">
          <Rocket className="text-midnight w-5 h-5" />
        </div>
        <span className="text-lg font-bold tracking-tighter">ZENITH AI</span>
      </div>
      <div className="flex items-center gap-8">
        <a href="#" className="text-sm text-white/60 hover:text-white transition-colors">Features</a>
        <Button variant="secondary" className="px-5 py-2 text-sm" onClick={() => onStart('signin')}>Sign In</Button>
      </div>
    </nav>

    {/* Hero Section */}
    <main className="flex-1 flex flex-col items-center justify-center px-6 text-center relative overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] cosmic-gradient opacity-30 pointer-events-none" />
      
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="relative z-10 max-w-4xl"
      >
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-neon-cyan mb-8">
          <Sparkles size={14} />
          <span>NEXT-GEN VIDEO INTELLIGENCE</span>
        </div>
        <h1 className="text-7xl md:text-8xl font-bold tracking-tight mb-6 leading-[1.1]">
          Summarize the <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-neon-cyan to-neon-purple">World of Video</span>
        </h1>
        <p className="text-xl text-white/60 mb-10 max-w-2xl mx-auto leading-relaxed">
          Zenith AI transforms hours of footage into actionable insights in seconds. 
          The ultimate tool for creators and researchers.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button variant="neon" className="text-lg px-10 py-4" onClick={() => onStart('signup')}>
            Start for Free <ArrowRight size={20} />
          </Button>
          <Button variant="ghost" className="text-lg px-10 py-4" onClick={onWatchDemo}>
            Watch Demo
          </Button>
        </div>
      </motion.div>

      {/* Astronaut Illustration Placeholder */}
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.4, duration: 1 }}
        className="mt-20 relative"
      >
        <div className="w-64 h-64 md:w-80 md:h-80 rounded-full bg-gradient-to-b from-white/10 to-transparent flex items-center justify-center border border-white/5 relative">
          <div className="absolute inset-0 bg-neon-purple/20 blur-3xl rounded-full animate-pulse" />
          <Rocket size={120} className="text-white/20 rotate-45" />
          <div className="absolute -top-4 -right-4 w-12 h-12 bg-neon-cyan/20 rounded-full blur-xl" />
          <div className="absolute bottom-8 -left-8 w-16 h-16 bg-neon-purple/30 rounded-full blur-2xl" />
        </div>
      </motion.div>
    </main>

    {/* 3-Step Guide */}
    <section className="py-24 px-6 bg-white/[0.02] border-t border-white/5">
      <div className="max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">The Zenith Workflow</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
          {[
            { icon: Upload, title: 'Upload', desc: 'Drop your video files into our secure cloud storage.' },
            { icon: Zap, title: 'Summarize', desc: 'Our AI engines extract the core essence of your content.' },
            { icon: FileText, title: 'Transcript', desc: 'Receive a searchable, high-fidelity transcript instantly.' }
          ].map((step, i) => (
            <div key={i} className="flex flex-col items-center text-center group">
              <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-6 group-hover:border-neon-cyan/50 transition-colors">
                <step.icon className="text-neon-cyan" size={32} />
              </div>
              <h3 className="text-xl font-bold mb-3">{step.title}</h3>
              <p className="text-white/50">{step.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* Footer */}
    <footer className="py-12 px-8 border-t border-white/5 text-center text-white/40 text-sm">
      <p>&copy; 2024 Zenith AI. All rights reserved.</p>
    </footer>
  </div>
);

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
  onOpenHistory,
}: {
  jobId: string | null;
  onComplete: (job: VideoJob) => void;
  onOpenHistory: () => void;
}) => {
  const [job, setJob] = useState<VideoJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
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

        setErrorMessage(error instanceof Error ? error.message : 'Unable to load job status');
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
  }, [jobId, onComplete]);

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

  const handleExportPDF = () => {
    window.print();
  };

  const actionItems = job?.action_items ?? [];
  const summaryText = job?.summary ?? 'No summary generated yet.';
  const transcriptEntries = useMemo(() => {
    const transcript = job?.transcript ?? '';
    const lines = transcript
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (!searchTerm.trim()) {
      return lines;
    }

    const normalizedSearch = searchTerm.toLowerCase();
    return lines.filter((line) => line.toLowerCase().includes(normalizedSearch));
  }, [job?.transcript, searchTerm]);

  const handleCopy = () => {
    navigator.clipboard.writeText(summaryText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
            <img 
              src="https://picsum.photos/seed/space/1280/720" 
              alt="Video Preview" 
              className="w-full h-full object-cover opacity-60"
              referrerPolicy="no-referrer"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-20 h-20 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 group-hover:scale-110 transition-transform cursor-pointer">
                <Play className="text-white fill-white ml-1" size={32} />
              </div>
            </div>
            {/* Controls Overlay */}
            <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-midnight to-transparent">
              <div className="h-1.5 w-full bg-white/20 rounded-full mb-4 overflow-hidden">
                <div className="h-full w-1/3 bg-neon-cyan" />
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-4">
                  <Play size={18} />
                  <span>04:12 / 12:05</span>
                </div>
                <div className="flex items-center gap-4">
                  <Settings size={18} />
                  <LayoutDashboard size={18} />
                </div>
              </div>
            </div>
          </div>

          <div className="glass-panel p-6">
            <h3 className="font-bold mb-4 flex items-center gap-2">
              <Zap size={18} className="text-neon-cyan" />
              Quick Stats
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                <p className="text-xs text-white/40 mb-1">Transcript Lines</p>
                <p className="text-lg font-bold">{transcriptEntries.length}</p>
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
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedJob, setSelectedJob] = useState<VideoJob | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
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
      setJobsError(error instanceof Error ? error.message : 'Unable to load video jobs');
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  const handleAuthSuccess = () => {
    setUser({
      name: 'Neil Armstrong',
      email: 'commander@zenith.ai',
      isPro: true
    });
    setCurrentScreen('dashboard');
  };

  const handleLogout = () => {
    setUser(null);
    setCurrentScreen('landing');
  };

  const handleUpdateUser = (updates: Partial<UserProfile>) => {
    setUser(prev => prev ? { ...prev, ...updates } : null);
  };

  const handleUpload = useCallback(async (file: File, languageHint: LanguageHint) => {
    setIsUploading(true);
    setJobsError(null);

    try {
      const response = await uploadVideo(file, languageHint);
      setActiveJobId(response.id);
      setSelectedJob(null);
      setCurrentScreen('analysis');
      void loadJobs();
    } catch (error) {
      setJobsError(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  }, [loadJobs]);

  const handleOpenJob = useCallback(async (job: VideoJob) => {
    setActiveJobId(job.id);
    try {
      const detailedJob = await fetchVideoJob(job.id);
      setSelectedJob(detailedJob);
      setCurrentScreen(detailedJob.status === 'completed' ? 'review' : 'analysis');
    } catch {
      setSelectedJob(job);
      setCurrentScreen(job.status === 'completed' ? 'review' : 'analysis');
    }
  }, []);

  const handleAnalysisComplete = useCallback(async (job: VideoJob) => {
    setSelectedJob(job);
    setActiveJobId(job.id);
    await loadJobs();
    setCurrentScreen('review');
  }, [loadJobs]);

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
