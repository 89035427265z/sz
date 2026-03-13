// =============================================================================
// KARI.Самозанятые — Точка входа приложения
// Файл: App.js
// =============================================================================
//
// Что здесь происходит при старте:
//   1. AuthProvider восстанавливает сессию из SecureStore
//   2. AppNavigator определяет начальный экран (авторизация / главная)
//   3. Push-уведомления инициализируются автоматически через AppNavigator
//
// =============================================================================

import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider } from './src/hooks/useAuth';
import AppNavigator from './src/navigation/AppNavigator';

export default function App() {
  return (
    <AuthProvider>
      {/* Малиновый статус-бар в стиле бренда KARI */}
      <StatusBar style="light" backgroundColor="#A01F72" />

      {/* AppNavigator содержит NavigationContainer + push-инициализацию */}
      <AppNavigator />
    </AuthProvider>
  );
}
