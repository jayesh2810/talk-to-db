import React, { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [credentials, setCredentials] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)

  // Check localStorage for existing session
  useEffect(() => {
    const stored = localStorage.getItem('kumo_auth')
    if (stored) {
      try {
        const { username, password } = JSON.parse(stored)
        setCredentials({ username, password })
        setIsAuthenticated(true)
      } catch (e) {
        localStorage.removeItem('kumo_auth')
      }
    }
  }, [])

  const login = async (username, password) => {
    setLoading(true)
    // We don't actually call an API to "login" in the traditional sense because
    // we are using Basic Auth, so we just need to store them to include in headers.
    // However, we should verify them against the backend to be sure.
    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        headers: {
          'Authorization': 'Basic ' + btoa(`${username}:${password}`)
        },
      })

      if (response.ok) {
        setCredentials({ username, password })
        setIsAuthenticated(true)
        localStorage.setItem('kumo_auth', JSON.stringify({ username, password }))
        return true
      } else {
        throw new Error('Invalid credentials')
      }
    } catch (err) {
      throw err
    } finally {
      setLoading(false)
    }
  }

  const logout = () => {
    setIsAuthenticated(false)
    setCredentials({ username: '', password: '' })
    localStorage.removeItem('kumo_auth')
  }

  const getAuthHeader = () => {
    if (isAuthenticated) {
      return { 'Authorization': 'Basic ' + btoa(`${credentials.username}:${credentials.password}`) }
    }
    return {}
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout, getAuthHeader, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
