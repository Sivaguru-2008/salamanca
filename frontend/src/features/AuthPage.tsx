import React, { useState } from 'react';
import { Sparkles, Mail, Lock, User as UserIcon, ArrowRight, Loader2 } from 'lucide-react';
import { apiService } from '../services/apiService';
import { User } from '../types';

interface AuthPageProps {
  onAuthenticated: (user: User) => void;
}

const describeAuthError = (error: unknown, fallback: string) => {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as any).response;
    if (response?.status === 401) return 'Invalid email or password.';
    if (response?.status === 409) return 'An account with this email already exists.';
    const detail = response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
};

export const AuthPage: React.FC<AuthPageProps> = ({ onAuthenticated }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);

    try {
      if (mode === 'register') {
        await apiService.register(email.trim(), password, fullName.trim());
      }
      await apiService.login(email.trim(), password);
      const user = await apiService.getCurrentUser();
      if (!user) throw new Error('Signed in, but the profile could not be loaded.');
      onAuthenticated(user);
    } catch (err) {
      setError(
        describeAuthError(
          err,
          mode === 'login' ? 'Sign-in failed. Is the backend running?' : 'Registration failed.',
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#faf8f5] flex items-center justify-center p-6 select-none">
      <div className="w-full max-w-md space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
        {/* Brand */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 bg-[#0a1120] text-white px-4 py-2 rounded-full">
            <Sparkles size={14} className="text-[#c09a5f]" />
            <span className="font-serif text-sm font-semibold tracking-wide">FIOS</span>
          </div>
          <h1 className="font-serif text-3xl font-light text-brand-navy">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="text-xs text-brand-graphite/50">
            {mode === 'login'
              ? 'Sign in to access your financial intelligence studio.'
              : 'Register to start building your financial twin.'}
          </p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-white border border-black/5 rounded-2xl p-8 shadow-premium space-y-5"
        >
          {mode === 'register' && (
            <div className="flex flex-col gap-2">
              <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">
                Full Name
              </label>
              <div className="flex items-center gap-2 bg-black/5 rounded-lg px-3 focus-within:bg-white border border-transparent focus-within:border-[#c09a5f]/40 transition-all">
                <UserIcon size={14} className="text-brand-graphite/30 shrink-0" />
                <input
                  type="text"
                  required
                  autoComplete="name"
                  className="flex-1 bg-transparent outline-none py-2.5 text-xs font-semibold"
                  placeholder="Ada Lovelace"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">
              Email
            </label>
            <div className="flex items-center gap-2 bg-black/5 rounded-lg px-3 focus-within:bg-white border border-transparent focus-within:border-[#c09a5f]/40 transition-all">
              <Mail size={14} className="text-brand-graphite/30 shrink-0" />
              <input
                type="email"
                required
                autoComplete="email"
                className="flex-1 bg-transparent outline-none py-2.5 text-xs font-semibold"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">
              Password
            </label>
            <div className="flex items-center gap-2 bg-black/5 rounded-lg px-3 focus-within:bg-white border border-transparent focus-within:border-[#c09a5f]/40 transition-all">
              <Lock size={14} className="text-brand-graphite/30 shrink-0" />
              <input
                type="password"
                required
                minLength={8}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className="flex-1 bg-transparent outline-none py-2.5 text-xs font-semibold"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="border border-red-200 bg-red-500/5 text-rose-600 rounded-lg px-3 py-2.5 text-[11px] font-semibold leading-relaxed">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand-navy hover:bg-[#c09a5f] text-white py-3 rounded-full text-xs font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <>
                {mode === 'login' ? 'Sign in' : 'Create account'}
                <ArrowRight size={13} />
              </>
            )}
          </button>

          <div className="text-center text-[11px] text-brand-graphite/50 pt-1">
            {mode === 'login' ? (
              <>
                No account yet?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('register');
                    setError(null);
                  }}
                  className="text-[#c09a5f] font-bold hover:text-[#ad8449]"
                >
                  Register
                </button>
              </>
            ) : (
              <>
                Already registered?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('login');
                    setError(null);
                  }}
                  className="text-[#c09a5f] font-bold hover:text-[#ad8449]"
                >
                  Sign in
                </button>
              </>
            )}
          </div>
        </form>

        <p className="text-center text-[9px] text-brand-graphite/30 uppercase tracking-widest">
          Financial Intelligence Operating System
        </p>
      </div>
    </div>
  );
};
