// =============================================================================
// KARI.Самозанятые — Хук авторизации
// Файл: src/hooks/useAuth.js
// =============================================================================
//
// Управляет сессией пользователя:
//   • Восстановление токена из SecureStore при старте
//   • Вход через SMS-код → получение JWT
//   • Выход → очистка данных
//   • Регистрация push-токена после авторизации (отправка на бэкенд)
//
// =============================================================================

import { useState, useEffect, createContext, useContext } from 'react';
import * as SecureStore from 'expo-secure-store';

import { confirmSmsCode, registerPushToken, getProfile } from '../api/client';
import {
  registerForPushNotifications,
  setupNotificationHandlers,
  clearPushToken,
} from '../services/notifications';

const AuthContext = createContext(null);


export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null);    // данные пользователя
  const [token,   setToken]   = useState(null);    // JWT токен
  const [loading, setLoading] = useState(true);    // восстанавливаем сессию

  // ── При старте — восстановить сессию из SecureStore ──────────────────────
  useEffect(() => {
    (async () => {
      try {
        const savedToken = await SecureStore.getItemAsync('kari_token');
        const savedUser  = await SecureStore.getItemAsync('kari_user');
        if (savedToken && savedUser) {
          setToken(savedToken);
          setUser(JSON.parse(savedUser));
        }
      } catch (e) {
        // SecureStore недоступен на эмуляторе без подписи — игнорируем
      } finally {
        setLoading(false);
      }
    })();
  }, []);


  // ── Вход: SMS-код → JWT токен ─────────────────────────────────────────────
  const login = async (phone, code) => {
    const res = await confirmSmsCode(phone, code);
    const { access_token, user: userData } = res.data;

    // Сохраняем сессию
    await SecureStore.setItemAsync('kari_token', access_token);
    await SecureStore.setItemAsync('kari_user',  JSON.stringify(userData));

    setToken(access_token);
    setUser(userData);
    return userData;
  };


  // ── Обновить данные пользователя из бэкенда (вызывается после онбординга) ─
  const refreshUser = async () => {
    try {
      const res = await getProfile();
      const userData = res.data;
      await SecureStore.setItemAsync('kari_user', JSON.stringify(userData));
      setUser(userData);
    } catch (e) {
      console.warn('[Auth] refreshUser error:', e.message);
    }
  };


  // ── Выход — очищаем токен и push-токен ───────────────────────────────────
  const logout = async () => {
    await SecureStore.deleteItemAsync('kari_token');
    await SecureStore.deleteItemAsync('kari_user');
    await clearPushToken(); // Очищаем кеш push-токена — при следующем входе запросим снова
    setToken(null);
    setUser(null);
  };


  // ── Регистрация push-уведомлений ─────────────────────────────────────────
  /**
   * Вызывается из AppNavigator после успешной авторизации.
   * Получает Expo Push Token, отправляет на бэкенд, настраивает обработчики.
   *
   * navigationRef нужен для навигации при тапе на уведомление.
   */
  const registerPushIfNeeded = async (navigationRef) => {
    try {
      // 1. Получаем Expo Push Token (запросит разрешение если нужно)
      const pushToken = await registerForPushNotifications();

      if (pushToken) {
        // 2. Отправляем токен на бэкенд (PUT /users/me/fcm-token)
        await registerPushToken(pushToken);
        console.log('[Auth] Push-токен зарегистрирован на бэкенде');
      }

      // 3. Настраиваем обработчики тапов на уведомления (работают и без токена)
      setupNotificationHandlers(navigationRef);

    } catch (e) {
      // Push — не критичная функция, не ломаем основной флоу при ошибке
      console.warn('[Auth] Push регистрация не удалась:', e.message);
    }
  };


  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        logout,
        refreshUser,           // вызывается после онбординга — AppNavigator сам переключится
        isLoggedIn: !!token,
        registerPushIfNeeded,  // используется в AppNavigator
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
