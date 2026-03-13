// =============================================================================
// KARI.Самозанятые — Страница входа (авторизация по SMS)
// =============================================================================
//
// Логика входа:
//   Шаг 1: Ввод номера телефона → POST /auth/send-code
//   Шаг 2: Ввод 6-значного SMS-кода → POST /auth/verify-code
//   После успеха: токен сохраняется, редирект на /dashboard

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '../api/client.js'
import { useAuth } from '../hooks/useAuth.js'
import KariLogo from '../components/KariLogo.jsx'

export default function LoginPage() {
  const navigate  = useNavigate()
  const { login } = useAuth()

  // Шаги: 'phone' или 'code'
  const [step,      setStep]      = useState('phone')
  const [phone,     setPhone]     = useState('')
  const [code,      setCode]      = useState('')
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')
  const [debugCode, setDebugCode] = useState('') // только в DEBUG-режиме

  // ===== Шаг 1: Отправить SMS =====
  const handleSendCode = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { data } = await authAPI.sendCode(phone)
      // В DEBUG-режиме бэкенд возвращает код прямо в ответе
      if (data.debug_code) {
        setDebugCode(data.debug_code)
      }
      setStep('code')
    } catch (err) {
      const msg = err.response?.data?.detail
      if (msg === 'Пользователь не найден') {
        setError('Телефон не найден в системе. Обратитесь к администратору.')
      } else {
        setError(msg || 'Ошибка отправки SMS. Попробуйте позже.')
      }
    } finally {
      setLoading(false)
    }
  }

  // ===== Шаг 2: Подтвердить код =====
  const handleVerifyCode = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { data } = await authAPI.verifyCode(phone, code)
      login(data.access_token, data.user)
      navigate('/dashboard')
    } catch (err) {
      const msg = err.response?.data?.detail
      if (msg?.includes('Неверный код')) {
        setError('Неверный код. Проверьте SMS и попробуйте снова.')
      } else if (msg?.includes('Превышено')) {
        setError('Превышено число попыток. Запросите новый код.')
        setStep('phone')
      } else {
        setError(msg || 'Ошибка проверки кода.')
      }
    } finally {
      setLoading(false)
    }
  }

  // Форматирование номера телефона при вводе
  const handlePhoneChange = (e) => {
    let val = e.target.value.replace(/\D/g, '')
    if (val.startsWith('8')) val = '7' + val.slice(1)
    if (val.length > 11) val = val.slice(0, 11)
    if (val.length > 0) val = '+' + val
    setPhone(val)
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>

        {/* Логотип KARI */}
        <div style={styles.logoWrap}>
          <KariLogo height={52} />
          <div style={styles.logoSub}>Самозанятые</div>
        </div>

        <h1 style={styles.title}>
          {step === 'phone' ? 'Вход в систему' : 'Введите код из SMS'}
        </h1>

        <p style={styles.subtitle}>
          {step === 'phone'
            ? 'Введите номер телефона, зарегистрированный в системе'
            : `Код отправлен на ${phone}`}
        </p>

        {/* ===== Шаг 1: Телефон ===== */}
        {step === 'phone' && (
          <form onSubmit={handleSendCode} style={styles.form}>
            <div style={styles.field}>
              <label style={styles.label}>Номер телефона</label>
              <input
                type="tel"
                value={phone}
                onChange={handlePhoneChange}
                placeholder="+7 (999) 999-99-99"
                style={styles.input}
                required
                autoFocus
              />
            </div>

            {error && <div style={styles.error}>{error}</div>}

            <button
              type="submit"
              style={loading ? {...styles.btn, ...styles.btnDisabled} : styles.btn}
              disabled={loading || phone.replace(/\D/g,'').length < 11}
            >
              {loading ? 'Отправляем SMS...' : 'Получить SMS-код'}
            </button>
          </form>
        )}

        {/* ===== Шаг 2: Код ===== */}
        {step === 'code' && (
          <form onSubmit={handleVerifyCode} style={styles.form}>

            {/* DEBUG: показываем код прямо на экране если бэкенд вернул */}
            {debugCode && (
              <div style={styles.debugBox}>
                🛠️ DEBUG-режим: ваш код <strong>{debugCode}</strong>
              </div>
            )}

            <div style={styles.field}>
              <label style={styles.label}>Код из SMS</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g,''))}
                placeholder="------"
                style={{...styles.input, ...styles.codeInput}}
                required
                autoFocus
              />
            </div>

            {error && <div style={styles.error}>{error}</div>}

            <button
              type="submit"
              style={loading ? {...styles.btn, ...styles.btnDisabled} : styles.btn}
              disabled={loading || code.length !== 6}
            >
              {loading ? 'Проверяем...' : 'Войти'}
            </button>

            <button
              type="button"
              style={styles.btnBack}
              onClick={() => { setStep('phone'); setCode(''); setError(''); setDebugCode('') }}
            >
              ← Изменить номер
            </button>
          </form>
        )}

        {/* Подпись */}
        <div style={styles.footer}>
          KARI.Самозанятые © {new Date().getFullYear()}
        </div>
      </div>
    </div>
  )
}

// ===== Стили =====
const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #242D4A 0%, #3d2060 50%, #a91d7a 100%)',
    padding: '24px',
  },
  card: {
    background: '#fff',
    borderRadius: '16px',
    padding: '48px 40px',
    width: '100%',
    maxWidth: '420px',
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '8px',
  },
  logoWrap: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
    marginBottom: '8px',
  },
  logoSub: {
    fontSize: '11px',
    fontWeight: '700',
    letterSpacing: '4px',
    textTransform: 'uppercase',
    color: '#a91d7a',
    opacity: 0.8,
  },
  title: {
    fontSize: '22px',
    fontWeight: '800',
    color: '#1a1a1a',
    marginTop: '12px',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: '14px',
    color: '#6b7280',
    textAlign: 'center',
    marginBottom: '8px',
  },
  form: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    marginTop: '8px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '13px',
    fontWeight: '700',
    color: '#374151',
  },
  input: {
    border: '2px solid #e5e7eb',
    borderRadius: '8px',
    padding: '12px 16px',
    fontSize: '16px',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color .2s',
    width: '100%',
  },
  codeInput: {
    letterSpacing: '8px',
    fontSize: '24px',
    fontWeight: '800',
    textAlign: 'center',
  },
  btn: {
    background: '#a91d7a',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '14px',
    fontSize: '15px',
    fontWeight: '800',
    fontFamily: 'inherit',
    cursor: 'pointer',
    width: '100%',
    transition: 'background .2s',
  },
  btnDisabled: {
    background: '#d1d5db',
    cursor: 'not-allowed',
  },
  btnBack: {
    background: 'transparent',
    border: 'none',
    color: '#6b7280',
    cursor: 'pointer',
    fontSize: '13px',
    fontFamily: 'inherit',
    textDecoration: 'underline',
    padding: '4px',
    textAlign: 'center',
  },
  error: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    padding: '10px 14px',
    fontSize: '13px',
    color: '#dc2626',
  },
  debugBox: {
    background: '#fffbeb',
    border: '1px solid #fde68a',
    borderRadius: '8px',
    padding: '10px 14px',
    fontSize: '13px',
    color: '#92400e',
    textAlign: 'center',
  },
  footer: {
    marginTop: '24px',
    fontSize: '12px',
    color: '#9ca3af',
    textAlign: 'center',
  },
}
