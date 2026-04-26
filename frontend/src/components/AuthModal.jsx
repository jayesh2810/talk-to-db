import React, { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function AuthModal() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const { login, loading } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await login(username, password)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="fixed inset-0 z-[100] overflow-hidden bg-surface text-on-surface selection:bg-primary-container selection:text-on-primary-container">
      {/* Background Layer with Connectivity Visuals */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute inset-0 data-grid-bg opacity-30"></div>
        <div className="absolute top-[-10%] right-[-10%] w-[600px] h-[600px] bg-primary/10 blur-[120px] rounded-full"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] bg-tertiary/5 blur-[100px] rounded-full"></div>
        <svg className="absolute inset-0 w-full h-full opacity-10" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="line-grad" x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0"></stop>
              <stop offset="50%" stopColor="currentColor" stopOpacity="1"></stop>
              <stop offset="100%" stopColor="currentColor" stopOpacity="0"></stop>
            </linearGradient>
          </defs>
          <line className="text-primary" stroke="url(#line-grad)" strokeWidth="0.5" x1="10%" x2="90%" y1="20%" y2="80%"></line>
          <line className="text-tertiary" stroke="url(#line-grad)" strokeWidth="0.5" x1="80%" x2="20%" y1="10%" y2="90%"></line>
          <circle cx="30%" cy="40%" fill="white" fillOpacity="0.2" r="2"></circle>
          <circle cx="70%" cy="60%" fill="white" fillOpacity="0.2" r="2"></circle>
        </svg>
      </div>

      {/* Main Content Canvas */}
      <main className="relative z-10 flex min-h-screen items-center justify-center p-gutter">
        <div className="w-full max-w-[480px]">
          {/* Header Section */}
          <div className="mb-xl text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-slate-900/80 border border-white/10 mb-md shadow-2xl">
              <span className="material-symbols-outlined text-primary text-4xl">hub</span>
            </div>
            <h1 className="font-headline-xl text-headline-xl text-on-surface tracking-tighter">DataCommand AI</h1>
            <p className="font-body-md text-body-md text-on-surface-variant mt-xs">Access your intellectual command center</p>
          </div>

          {/* Login Card */}
          <div className="glass-panel rounded-xl shadow-[0_20px_50px_rgba(2,6,23,0.7)] p-xl">
            <form onSubmit={handleSubmit} className="space-y-lg">
              {/* Email Field */}
              <div className="space-y-xs">
                <label className="font-label-md text-label-md text-on-surface-variant uppercase tracking-widest" htmlFor="email">Enterprise Email</label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-md flex items-center pointer-events-none">
                    <span className="material-symbols-outlined text-outline text-[20px] group-focus-within:text-primary transition-colors">mail</span>
                  </div>
                  <input 
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg py-3 pl-11 pr-md font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-on-surface placeholder:text-outline/50" 
                    id="email" 
                    name="email" 
                    placeholder="name@company.com" 
                    type="email"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="space-y-xs">
                <div className="flex justify-between items-center">
                  <label className="font-label-md text-label-md text-on-surface-variant uppercase tracking-widest" htmlFor="password">Security Key</label>
                  <a className="font-label-md text-label-md text-primary hover:text-primary-fixed transition-colors" href="#">Forgot Access?</a>
                </div>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-md flex items-center pointer-events-none">
                    <span className="material-symbols-outlined text-outline text-[20px] group-focus-within:text-primary transition-colors">lock</span>
                  </div>
                  <input 
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg py-3 pl-11 pr-md font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-on-surface placeholder:text-outline/50" 
                    id="password" 
                    name="password" 
                    placeholder="••••••••••••" 
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <div className="absolute inset-y-0 right-0 pr-md flex items-center cursor-pointer text-outline hover:text-on-surface transition-colors">
                    <span className="material-symbols-outlined text-[20px]">visibility</span>
                  </div>
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-error/10 border border-error/20 text-xs text-error text-center animate-in fade-in slide-in-from-top-1">
                  {error}
                </div>
              )}

              {/* Submit Button */}
              <button 
                className="w-full bg-primary hover:bg-primary-container text-on-primary font-label-md text-label-md py-4 rounded-lg shadow-xl shadow-primary/10 transition-all active:scale-[0.98] flex items-center justify-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed" 
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  <div className="flex items-center justify-center gap-2">
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                    </svg>
                    Initializing...
                  </div>
                ) : (
                  <>
                    <span>Initialize Command</span>
                    <span className="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">arrow_forward</span>
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="relative my-xl">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-outline-variant"></span>
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-[#151c2c] px-md font-label-md text-on-surface-variant uppercase tracking-widest">Or authenticate via</span>
              </div>
            </div>

            {/* SSO Options */}
            <div className="grid grid-cols-2 gap-md">
              <button className="flex items-center justify-center gap-2 py-3 px-md border border-outline-variant rounded-lg font-label-md text-label-md text-on-surface hover:bg-white/5 transition-colors group">
                <img alt="Google" className="w-5 h-5 grayscale group-hover:grayscale-0 transition-all" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDQo8YMVf1T6qyAclvnzRHRvKIvmnIUyTd8ob7Sb-548C-bk7nLc-wqrU25juvDiN3B92EskHj9hQTjhem_Vy4UKe0tqnYWGzECQa8ZJkoDOllLs0qOwfvLJPuxtAVYY_cSj78rqYL6z9WNGOiLWKCGxz6SOmZZs09u9cbXbGc41Td8bvALa2vefFlnxyJxSyzPesno7trOL3jxXPR-RIv_I3M7xPTTIf_OERbpS8r_DgvmAZV9IWaTCpOej-8AdOG7iEWTXESvFsLC"/>
                <span>Google</span>
              </button>
              <button className="flex items-center justify-center gap-2 py-3 px-md border border-outline-variant rounded-lg font-label-md text-label-md text-on-surface hover:bg-white/5 transition-colors group">
                <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors">security</span>
                <span>Okta SSO</span>
              </button>
            </div>
          </div>

          {/* Footer Links */}
          <div className="mt-xl flex flex-col items-center gap-md">
            <p className="font-body-md text-body-md text-on-surface-variant">
              New to DataCommand? <a className="text-primary font-semibold hover:underline" href="#">Request Provisioning</a>
            </p>
            <div className="flex gap-lg">
              <a className="font-label-md text-[10px] text-outline uppercase tracking-widest hover:text-on-surface-variant transition-colors" href="#">Trust Center</a>
              <a className="font-label-md text-[10px] text-outline uppercase tracking-widest hover:text-on-surface-variant transition-colors" href="#">Privacy Policy</a>
              <a className="font-label-md text-[10px] text-outline uppercase tracking-widest hover:text-on-surface-variant transition-colors" href="#">System Status</a>
            </div>
          </div>
        </div>
      </main>

      {/* Visual Accents */}
      <div className="fixed bottom-margin right-margin z-0 pointer-events-none hidden lg:block">
        <div className="glass-panel p-md rounded-xl w-64 shadow-2xl rotate-3 translate-y-10 opacity-40">
          <div className="flex items-center gap-sm mb-xs">
            <span className="w-2 h-2 rounded-full bg-tertiary"></span>
            <div className="h-2 w-20 bg-outline-variant rounded"></div>
          </div>
          <div className="space-y-xs">
            <div className="h-1.5 w-full bg-outline-variant/30 rounded"></div>
            <div className="h-1.5 w-4/5 bg-outline-variant/30 rounded"></div>
          </div>
        </div>
      </div>
      <div className="fixed top-margin left-margin z-0 pointer-events-none hidden lg:block">
        <div className="glass-panel p-md rounded-xl w-48 shadow-2xl -rotate-6 -translate-y-5 opacity-30">
          <div className="flex justify-between items-center mb-sm">
            <div className="h-3 w-12 bg-primary/20 rounded"></div>
            <span className="material-symbols-outlined text-primary/40 text-sm">query_stats</span>
          </div>
          <div className="flex items-end gap-1 h-8">
            <div className="flex-1 bg-primary/10 h-1/2 rounded-t-sm"></div>
            <div className="flex-1 bg-primary/20 h-3/4 rounded-t-sm"></div>
            <div className="flex-1 bg-primary/30 h-full rounded-t-sm"></div>
            <div className="flex-1 bg-primary/10 h-1/3 rounded-t-sm"></div>
          </div>
        </div>
      </div>
    </div>
  )
}
