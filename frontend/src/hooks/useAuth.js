// =============================================================================
// KARI.Самозанятые — Хук авторизации
// =============================================================================
//
// Хранит JWT-токен в localStorage.
// Токен выдаётся бэкендом при успешном входе по SMS.
//
// Использование:
//   const { token, user, isLoggedIn, login, logout } = useAuth()

import { useState, useCallback } from 'react'

const TOKEN_KEY = 'kari_token'
const USER_KEY  = 'kari_user'

export function useAuth() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user,  setUser]  = useState(() => {
    try {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch { return null }
  })

  // Сохранить токен и данные пользователя после входа
  const login = useCallback((accessToken, userData) => {
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY, JSON.stringify(userData))
    setToken(accessToken)
    setUser(userData)
  }, [])

  // Выход: очищаем localStorage
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  return {
    token,
    user,
    isLoggedIn: Boolean(token),
    login,
    logout,
  }
}
