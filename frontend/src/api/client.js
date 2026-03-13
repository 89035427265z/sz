// =============================================================================
// KARI.Самозанятые — HTTP-клиент для запросов к бэкенду
// =============================================================================
//
// Использует axios. Автоматически добавляет Bearer-токен из localStorage.
// При 401 (токен устарел) — разлогинивает пользователя.

import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

// Создаём экземпляр axios с базовым URL
const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
})

// Interceptor запросов: добавляем JWT-токен
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('kari_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Interceptor ответов: при 401 — выходим из системы
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('kari_token')
      localStorage.removeItem('kari_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ===== Методы API =====

// Авторизация
export const authAPI = {
  sendCode:   (phone)        => client.post('/auth/send-code',   { phone }),
  verifyCode: (phone, code)  => client.post('/auth/verify-code', { phone, code }),
  getMe:      ()             => client.get('/auth/me'),
  logout:     ()             => client.post('/auth/logout'),
}

// Пользователи
export const usersAPI = {
  getList:     (params) => client.get('/users/',       { params }),
  getExecutors:(params) => client.get('/users/executors', { params }),
  getUser:     (id)     => client.get(`/users/${id}`),
  block:       (id, reason) => client.post(`/users/${id}/block`, { reason }),
  unblock:     (id)     => client.post(`/users/${id}/unblock`),
}

// Задания
export const tasksAPI = {
  getList:   (params) => client.get('/tasks/',          { params }),
  getExchange:(params)=> client.get('/tasks/exchange',  { params }),
  getTask:   (id)     => client.get(`/tasks/${id}`),
  create:    (data)   => client.post('/tasks/', data),
  update:    (id, data) => client.put(`/tasks/${id}`, data),
  publish:   (id)     => client.post(`/tasks/${id}/publish`),
  accept:    (id)     => client.post(`/tasks/${id}/accept`),
  reject:    (id, reason) => client.post(`/tasks/${id}/reject`, { reason }),
  cancel:    (id)     => client.post(`/tasks/${id}/cancel`),
}

// Выплаты
export const paymentsAPI = {
  getList:          (params) => client.get('/payments/',           { params }),
  getPayment:       (id)     => client.get(`/payments/${id}`),
  getRegistries:    (params) => client.get('/payments/registries/',{ params }),
  getRegistry:      (id)     => client.get(`/payments/registries/${id}`),
  uploadRegistry:   (file)   => {
    const form = new FormData()
    form.append('file', file)
    return client.post('/payments/registries/', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  approveRegistry:  (id)     => client.post(`/payments/registries/${id}/approve`),
  exportRegistry:   (id)     => client.get(`/payments/registries/${id}/export`, {
    responseType: 'blob'
  }),
  getReceipts:      (params) => client.get('/payments/receipts/', { params }),
}

// ФНС
export const fnsAPI = {
  checkInn:         (inn)    => client.get(`/fns/check/${inn}`),
  checkUser:        (userId) => client.post(`/fns/check-user/${userId}`),
  checkAllUsers:    ()       => client.post('/fns/check-all-users'),
  checkAllReceipts: ()       => client.post('/fns/receipts/check-all'),
  checkReceipt:     (id)     => client.post(`/fns/receipts/${id}/check`),
  cancelReceipt:    (id, reason) => client.post(`/fns/receipts/${id}/cancel?reason=${encodeURIComponent(reason)}`),
}

export default client
