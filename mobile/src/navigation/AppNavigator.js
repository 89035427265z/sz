// =============================================================================
// KARI.Самозанятые — Навигатор приложения
// Файл: src/navigation/AppNavigator.js
// =============================================================================
//
// Структура навигации:
//   Auth Stack:
//     • AuthScreen       — ввод номера телефона + SMS-код
//     • OnboardingScreen — ввод ФИО + ИНН + проверка ФНС
//
//   Main (после авторизации):
//     BottomTabs:
//       • Главная  → HomeScreen
//       • Задания  → TasksStack (TasksList → TaskDetail → SubmitTask)
//       • Кошелёк → WalletScreen
//       • Профиль → ProfileScreen
//
// Push-уведомления:
//   При старте регистрируем токен → отправляем на бэкенд → слушаем тапы.
//   Тап на уведомление открывает нужный экран через navigationRef.
//
// =============================================================================

import React, { useRef, useEffect } from 'react';
import { NavigationContainer }          from '@react-navigation/native';
import { createNativeStackNavigator }   from '@react-navigation/native-stack';
import { createBottomTabNavigator }     from '@react-navigation/bottom-tabs';
import { Text, ActivityIndicator, View } from 'react-native';

import { useAuth }     from '../hooks/useAuth';
import { clearBadge }  from '../services/notifications';

import AuthScreen            from '../screens/AuthScreen';
import OnboardingScreen      from '../screens/OnboardingScreen';
import HomeScreen            from '../screens/HomeScreen';
import TasksScreen           from '../screens/TasksScreen';
import TaskDetailScreen      from '../screens/TaskDetailScreen';
import SubmitTaskScreen      from '../screens/SubmitTaskScreen';
import WalletScreen          from '../screens/WalletScreen';
import ProfileScreen         from '../screens/ProfileScreen';
import StopListBlockedScreen from '../screens/StopListBlockedScreen';

// ─── Цвета бренда KARI ───────────────────────────────────────────────────────
const KARI_COLOR = '#A01F72';
const GRAY_COLOR = '#bdc3c7';

const Stack = createNativeStackNavigator();
const Tab   = createBottomTabNavigator();


// =============================================================================
// Вкладка «Задания» — вложенный стек: список → карточка → сдача работы
// =============================================================================
function TasksStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="TasksList"        component={TasksScreen}           />
      <Stack.Screen name="TaskDetail"       component={TaskDetailScreen}       />
      <Stack.Screen name="SubmitTask"       component={SubmitTaskScreen}       />
      {/* Экран блокировки стоп-листа — открывается из TaskDetail при 403 STOP_LIST_BLOCKED */}
      <Stack.Screen
        name="StopListBlocked"
        component={StopListBlockedScreen}
        options={{
          presentation: 'modal',          // Slide up как модальное окно
          gestureEnabled: true,
        }}
      />
    </Stack.Navigator>
  );
}


// =============================================================================
// Нижние вкладки (авторизованный пользователь)
// =============================================================================
function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor:   KARI_COLOR,
        tabBarInactiveTintColor: GRAY_COLOR,
        tabBarStyle: {
          backgroundColor: '#fff',
          borderTopColor:  '#f0f0f0',
          paddingBottom: 6,
          paddingTop:    6,
          height: 62,
        },
        tabBarLabelStyle: {
          fontSize:   11,
          fontWeight: '600',
        },
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          tabBarLabel: 'Главная',
          tabBarIcon: () => <Text style={{ fontSize: 22 }}>🏠</Text>,
        }}
      />
      <Tab.Screen
        name="Tasks"
        component={TasksStack}
        options={{
          tabBarLabel: 'Задания',
          tabBarIcon: () => <Text style={{ fontSize: 22 }}>📋</Text>,
        }}
      />
      <Tab.Screen
        name="Wallet"
        component={WalletScreen}
        options={{
          tabBarLabel: 'Кошелёк',
          tabBarIcon: () => <Text style={{ fontSize: 22 }}>💰</Text>,
        }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{
          tabBarLabel: 'Профиль',
          tabBarIcon: () => <Text style={{ fontSize: 22 }}>👤</Text>,
        }}
      />
    </Tab.Navigator>
  );
}


// =============================================================================
// Корневой навигатор — определяет стартовый экран по статусу авторизации
// и инициализирует push-уведомления
// =============================================================================
export default function AppNavigator() {
  const { isLoggedIn, user, loading, registerPushIfNeeded } = useAuth();

  // Ref для NavigationContainer — нужен чтобы из обработчика push-тапа
  // можно было перейти на нужный экран без прокидывания props
  const navigationRef = useRef(null);

  // ── Инициализируем push-уведомления после входа ──────────────────────────
  useEffect(() => {
    if (isLoggedIn && registerPushIfNeeded) {
      registerPushIfNeeded(navigationRef);
    }
  }, [isLoggedIn]);

  // ── При открытии приложения сбрасываем счётчик на иконке ─────────────────
  useEffect(() => {
    clearBadge();
  }, []);

  // ── Сплэш-экран пока восстанавливаем сессию ───────────────────────────────
  if (loading) {
    return (
      <View style={{
        flex: 1,
        justifyContent: 'center',
        alignItems:     'center',
        backgroundColor: KARI_COLOR,
      }}>
        <ActivityIndicator size="large" color="#fff" />
      </View>
    );
  }

  return (
    <NavigationContainer ref={navigationRef}>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!isLoggedIn ? (
          // ── Неавторизован ────────────────────────────────────────────────
          <>
            <Stack.Screen name="Auth"       component={AuthScreen}       />
            <Stack.Screen name="Onboarding" component={OnboardingScreen} />
          </>
        ) : !user?.inn ? (
          // ── Авторизован, но не заполнил ИНН — онбординг ─────────────────
          <Stack.Screen name="Onboarding" component={OnboardingScreen} />
        ) : (
          // ── Полноценный пользователь — главный экран с вкладками ─────────
          <Stack.Screen name="Main" component={MainTabs} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
