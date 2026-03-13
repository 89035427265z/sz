// =============================================================================
// KARI.Самозанятые — Сервис Push-уведомлений (Expo Notifications)
// Файл: src/services/notifications.js
// =============================================================================
//
// Как это работает:
//   1. При старте приложения вызываем registerForPushNotifications()
//   2. Получаем уникальный Expo Push Token устройства
//   3. Отправляем токен на бэкенд (PUT /users/me/fcm-token)
//   4. Бэкенд сохраняет токен и использует его для отправки push
//   5. При тапе на уведомление — навигируем на нужный экран
//
// Важно:
//   • Push-уведомления НЕ РАБОТАЮТ на симуляторе iOS — только реальное устройство
//   • На Android-эмуляторе могут работать если настроен Google Play Services
//   • В режиме разработки Expo Go push работают без доп. настройки!
//
// =============================================================================

import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// ─── Настройка поведения уведомлений ───────────────────────────────────────
// SDK 54: shouldShowAlert → shouldShowBanner + shouldShowList
// Оборачиваем в try-catch — в Expo Go push не критичны
try {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,   // показывать баннер (iOS 14+ / Android)
      shouldShowList:   true,   // показывать в центре уведомлений
      shouldPlaySound:  true,
      shouldSetBadge:   true,
    }),
  });
} catch (e) {
  // В Expo Go SDK 54 push-уведомления ограничены — это не критично
  console.warn('[Push] setNotificationHandler недоступен:', e.message);
}


// =============================================================================
// РЕГИСТРАЦИЯ И ПОЛУЧЕНИЕ ТОКЕНА
// =============================================================================

/**
 * Запрашивает разрешение и получает Expo Push Token.
 *
 * Возвращает строку токена вида "ExponentPushToken[xxxxx]" или null при ошибке.
 * Токен кешируется в SecureStore — не запрашиваем повторно при каждом запуске.
 */
export async function registerForPushNotifications() {
  // Push-уведомления работают только на реальных устройствах
  if (!Device.isDevice) {
    console.warn('[Push] Симулятор/эмулятор — push-уведомления недоступны');
    return null;
  }

  // Проверяем кешированный токен — если есть, возвращаем его
  try {
    const cached = await SecureStore.getItemAsync('kari_push_token');
    if (cached) {
      console.log('[Push] Токен из кеша:', cached.substring(0, 40) + '...');
      return cached;
    }
  } catch (e) {
    // SecureStore недоступен — продолжаем без кеша
  }

  // Запрашиваем разрешение на уведомления
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.warn('[Push] Пользователь отказал в разрешении на уведомления');
    return null;
  }

  // На Android нужен отдельный канал уведомлений
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('kari-default', {
      name:               'KARI.Самозанятые',
      importance:          Notifications.AndroidImportance.MAX,
      vibrationPattern:    [0, 250, 250, 250],
      lightColor:          '#A01F72',
      sound:               'default',
      enableVibrate:       true,
    });

    // Отдельный канал для выплат — важные уведомления
    await Notifications.setNotificationChannelAsync('kari-payments', {
      name:               'Выплаты KARI',
      importance:          Notifications.AndroidImportance.HIGH,
      vibrationPattern:    [0, 500, 200, 500],
      lightColor:          '#27AE60',
      sound:               'default',
      enableVibrate:       true,
    });
  }

  // Получаем Expo Push Token
  try {
    const tokenData = await Notifications.getExpoPushTokenAsync({
      // projectId из app.json / Expo — для продакшена нужен Expo account
      // В разработке через Expo Go можно не указывать
    });
    const token = tokenData.data;

    // Кешируем токен в SecureStore
    try {
      await SecureStore.setItemAsync('kari_push_token', token);
    } catch (e) {
      // Не критично — продолжаем без кеша
    }

    console.log('[Push] Токен получен:', token.substring(0, 40) + '...');
    return token;

  } catch (error) {
    console.error('[Push] Ошибка получения токена:', error.message);
    return null;
  }
}


// =============================================================================
// ОБРАБОТЧИКИ УВЕДОМЛЕНИЙ
// =============================================================================

/**
 * Настраивает обработчики уведомлений для навигации.
 *
 * Вызывается один раз в App.js.
 *
 * Аргументы:
 *   navigationRef — ref на NavigationContainer из AppNavigator
 *
 * Возвращает функцию очистки (для useEffect cleanup).
 */
export function setupNotificationHandlers(navigationRef) {
  // ── Обработчик ВХОДЯЩЕГО уведомления (приложение открыто) ─────────────────
  // Просто показываем — Notifications.setNotificationHandler уже настроен выше
  const foregroundSub = Notifications.addNotificationReceivedListener(
    (notification) => {
      const { title, body } = notification.request.content;
      console.log(`[Push] Получено: "${title}" — ${body}`);
    }
  );

  // ── Обработчик ТАПА по уведомлению ───────────────────────────────────────
  // Когда пользователь тапает на баннер — переходим на нужный экран
  const tapSub = Notifications.addNotificationResponseReceivedListener(
    (response) => {
      const data = response.notification.request.content.data || {};
      const { screen, taskId, event } = data;

      console.log(`[Push] Тап на уведомление: screen=${screen}, event=${event}, taskId=${taskId}`);

      // Переходим на нужный экран если навигатор готов
      if (!navigationRef?.current) return;

      if (screen === 'TaskDetail' && taskId) {
        // Открываем карточку конкретного задания
        navigationRef.current.navigate('Main', {
          screen:    'Tasks',
          params: {
            screen:  'TaskDetail',
            params:  { taskId },
          },
        });
      } else if (screen === 'Wallet') {
        // Открываем кошелёк (выплаты)
        navigationRef.current.navigate('Main', { screen: 'Wallet' });
      } else if (screen === 'Tasks') {
        // Открываем биржу заданий
        navigationRef.current.navigate('Main', { screen: 'Tasks' });

      } else if (screen === 'StopListBlocked') {
        // Открываем экран блокировки стоп-листа
        // Передаём reason и blocked_until чтобы показать правильный текст
        navigationRef.current.navigate('Main', {
          screen: 'Tasks',
          params: {
            screen: 'StopListBlocked',
            params: {
              stopData: {
                code:          'STOP_LIST_BLOCKED',
                reason:        data.reason       || 'manual',
                blocked_until: data.blocked_until || null,
              },
            },
          },
        });
      }
    }
  );

  // Возвращаем функцию очистки подписок
  return () => {
    foregroundSub.remove();
    tapSub.remove();
  };
}


// =============================================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// =============================================================================

/**
 * Сбрасывает счётчик непрочитанных уведомлений на иконке приложения.
 * Вызывать при открытии приложения или после просмотра уведомлений.
 */
export async function clearBadge() {
  try {
    await Notifications.setBadgeCountAsync(0);
  } catch (e) {
    // Не критично
  }
}

/**
 * Удаляет кешированный push-токен (например, при выходе из аккаунта).
 * При следующем входе токен будет запрошен заново.
 */
export async function clearPushToken() {
  try {
    await SecureStore.deleteItemAsync('kari_push_token');
  } catch (e) {
    // Не критично
  }
}
