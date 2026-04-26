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
    <div className="fixed inset-0 z-[100] overflow-hidden bg-slate-950 text-slate-200 selection:bg-indigo-500 selection:text-white">
      {/* Main Content Canvas */}
      <main className="relative z-10 flex min-h-screen items-center justify-center p-6 bg-slate-950">
        <div className="w-full max-w-md">
          {/* Header Section */}
          <div className="mb-8 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-indigo-600 text-white mb-4 shadow-lg shadow-indigo-500/20">
               <span className="material-symbols-outlined text-3xl">hub</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">DataCommand AI</h1>
            <p className="text-slate-400 mt-2">Enterprise Intelligence Engine</p>
          </div>

          {/* Login Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Email Field */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider" htmlFor="email">Enterprise Email</label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="material-symbols-outlined text-slate-500 text-lg group-focus-within:text-indigo-500 transition-colors">mail</span>
                  </div>
                  <input 
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg py-2.5 pl-10 pr-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 transition-all" 
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
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider" htmlFor="password">Security Key</label>
                  <a className="text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors" href="#">Forgot Access?</a>
                </div>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="material-symbols-outlined text-slate-500 text-lg group-focus-within:text-indigo-500 transition-colors">lock</span>
                  </div>
                  <input 
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg py-2.5 pl-10 pr-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 transition-all" 
                    id="password" 
                    name="password" 
                    placeholder="••••••••••••" 
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 text-center animate-in fade-in slide-in-from-top-1">
                  {error}
                </div>
              )}

              {/* Submit Button */}
              <button 
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-lg shadow-lg shadow-indigo-600/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed" 
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
            <div className="relative my-8">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-slate-800"></span>
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-slate-900 px-3 text-slate-500 uppercase tracking-widest font-medium">Or authenticate via</span>
              </div>
            </div>

            {/* SSO Options */}
            <div className="grid grid-cols-2 gap-4">
              <button className="flex items-center justify-center gap-2 py-2.5 px-4 border border-slate-800 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors group">
                <img alt="Google" className="w-4 h-4 grayscale group-hover:grayscale-0 transition-all" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDQo8YMVf1T6qyAclvnzRHRvKIvmnIUyTd8ob7Sb-548C-bk7nLc-wqrU25juvDiN3B92EskHj9hQTjhem_Vy4UKe0tqnYWGzECQa8ZJkoDOllLs0qOwfvLJPuxtAVYY_cSj78rqYL6z9WNGOiLWKCGxz6SOmZZs09u9cbXbGc41Td8bvALa2vefFlnxyJxSyzPesno7trOL3jxXPR-RIv_I3M7xPTTIf_OERbpS8r_DgvmAZV9IWaTCpOej-8AdOG7iEWTXESvFsLC"/>
                <span>Google</span>
              </button>
              <button className="flex items-center justify-center gap-2 py-2.5 px-4 border border-slate-800 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors group">
                <span className="material-symbols-outlined text-slate-500 group-hover:text-indigo-500 transition-colors text-lg">security</span>
                <span>Okta SSO</span>
              </button>
            </div>
          </div>

          {/* Footer Links */}
          <div className="mt-8 flex flex-col items-center gap-4">
            <p className="text-sm text-slate-500">
              New to DataCommand? <a className="text-indigo-400 font-medium hover:underline" href="#">Request Provisioning</a>
            </p>
            <div className="flex gap-6">
              <a className="text-[10px] text-slate-600 uppercase tracking-widest hover:text-slate-400 transition-colors" href="#">Trust Center</a>
              <a className="text-[10px] text-slate-600 uppercase tracking-widest hover:text-slate-400 transition-colors" href="#">Privacy Policy</a>
              <a className="text-[10px] text-slate-600 uppercase tracking-widest hover:text-slate-400 transition-colors" href="#">System Status</a>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
