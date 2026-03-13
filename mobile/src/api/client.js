// =============================================================================
// KARI.Самозанятые — API-клиент
// Файл: src/api/client.js
// =============================================================================
//
// Все запросы к бэкенду FastAPI.
// Автоматически добавляет JWT-токен к каждому запросу.
//
// =============================================================================

import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

// DEV: локальный бэкенд (телефон и компьютер в одной Wi-Fi сети)
// При деплое заменить на: 'https://api.kari-samozanyatye.ru/api/v1'
const BASE_URL = 'http://10.255.197.212:8000/api/v1';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Перехватчик запросов — добавляем JWT-токен ────────────────────────────
api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('kari_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});


// =============================================================================
// АВТОРИЗАЦИЯ
// =============================================================================

// Запросить SMS-код по номеру телефона
// Бэкенд: POST /auth/send-code
export const requestSmsCode = (phone) =>
  api.post('/auth/send-code', { phone });

// Подтвердить SMS-код, получить JWT-токен
// Бэкенд: POST /auth/verify-code
export const confirmSmsCode = (phone, code) =>
  api.post('/auth/verify-code', { phone, code });


// =============================================================================
// ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
// =============================================================================

// Получить профиль текущего пользователя
export const getProfile = () => api.get('/users/me');

// Обновить профиль (ИНН, ФИО, банковские реквизиты)
export const updateProfile = (data) => api.patch('/users/me', data);

// Проверить статус самозанятого в ФНС по ИНН
// Бэкенд: GET /fns/check/{inn}
export const checkFnsStatus = (inn) => api.get(`/fns/check/${inn}`);


// =============================================================================
// PUSH-УВЕДОМЛЕНИЯ
// =============================================================================

/**
 * Регистрирует Expo Push Token на бэкенде.
 * Вызывается после входа в систему.
 *
 * token — строка вида "ExponentPushToken[xxxxxxxxxxxxxxxx]"
 * Бэкенд сохранит его в user.fcm_token для последующей отправки push.
 */
export const registerPushToken = (token) =>
  api.put('/users/me/fcm-token', { fcm_token: token });


// =============================================================================
// ЗАДАНИЯ (БИРЖА)
// =============================================================================

// Получить биржу заданий (доступные задания в моём регионе)
// Бэкенд: GET /tasks/exchange
export const getTasks = (params) => api.get('/tasks/exchange', { params });

// Получить детали задания
export const getTask = (taskId) => api.get(`/tasks/${taskId}`);

// Взять задание (изменить статус на «в работе»)
// Бэкенд: POST /tasks/{id}/take
export const acceptTask = (taskId) =>
  api.post(`/tasks/${taskId}/take`);

// Отказаться от задания
// Бэкенд: POST /tasks/{id}/cancel
export const declineTask = (taskId) =>
  api.post(`/tasks/${taskId}/cancel`);

// Сдать задание (фото + геометка + комментарий)
export const submitTask = (taskId, formData) =>
  api.post(`/tasks/${taskId}/submit`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });


// =============================================================================
// КОШЕЛЁК / ВЫПЛАТЫ
// =============================================================================

// Получить историю выплат исполнителя
// Бэкенд: GET /payments/  (фильтр по текущему пользователю на бэкенде)
export const getWallet = () => api.get('/payments/');


// =============================================================================
// ДОКУМЕНТЫ (ЭДО)
// =============================================================================

// Получить мои договоры и акты
// Бэкенд: GET /documents/
export const getDocuments = () => api.get('/documents/');

// Запросить SMS-код для подписания документа
export const requestDocumentSign = (docId) =>
  api.post(`/documents/${docId}/sign/request`);

// Подписать документ кодом из SMS
export const confirmDocumentSign = (docId, code) =>
  api.post(`/documents/${docId}/sign/confirm`, { code });


export default api;
