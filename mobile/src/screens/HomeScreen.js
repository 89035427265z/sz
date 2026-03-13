// Главный экран исполнителя: сводка, активное задание, уведомления
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, RefreshControl, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../hooks/useAuth';
import { getTasks, getWallet } from '../api/client';

const KARI  = '#A01F72';
const DARK  = '#242D4A';
const GREEN = '#27ae60';
const WARN  = '#e67e22';

// Демо-данные для предпросмотра (без бэкенда)
const DEMO_ACTIVE = {
  id: 'task-001',
  title: 'Уборка торгового зала',
  store: 'ТЦ «Карамель»',
  address: 'г. Иркутск, ул. Байкальская, 253А',
  amount: 1500,
  deadline: '2026-04-01',
  status: 'in_progress',
};

const DEMO_BALANCE = { amount: 12400, pending: 3700 };

const DEMO_HISTORY = [
  { id: 1, title: 'Выкладка весенней коллекции', amount: 2200, date: '28.03.2026', status: 'paid' },
  { id: 2, title: 'Уборка зала после акции',     amount: 1500, date: '25.03.2026', status: 'paid' },
];

export default function HomeScreen({ navigation }) {
  const { user }  = useAuth();
  const [activeTask, setActiveTask]   = useState(DEMO_ACTIVE);
  const [balance, setBalance]         = useState(DEMO_BALANCE);
  const [recentPayments, setRecent]   = useState(DEMO_HISTORY);
  const [refreshing, setRefreshing]   = useState(false);
  const [isDemo, setIsDemo]           = useState(true);

  // Загрузка данных с бэкенда
  const loadData = async () => {
    try {
      const [tasksRes, walletRes] = await Promise.all([
        getTasks({ status: 'in_progress', limit: 1 }),
        getWallet(),
      ]);
      setActiveTask(tasksRes.data.items?.[0] || null);
      setBalance(walletRes.data);
      setIsDemo(false);
    } catch {
      // Нет соединения с бэкендом — показываем демо
    }
  };

  useEffect(() => { loadData(); }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  // Первая буква имени для аватара
  const initials = user?.full_name?.charAt(0)?.toUpperCase() || '?';
  const firstName = user?.full_name?.split(' ')?.[1] || user?.full_name || 'Исполнитель';

  const formatAmount = (n) => n?.toLocaleString('ru-RU') + ' ₽';

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <ScrollView
        style={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={KARI} />}
      >
        {/* Шапка */}
        <View style={s.header}>
          <View>
            <Text style={s.greeting}>Привет, {firstName}! 👋</Text>
            <Text style={s.subGreeting}>Иркутский регион · Пилот Апрель 2026</Text>
          </View>
          <View style={s.avatar}>
            <Text style={s.avatarText}>{initials}</Text>
          </View>
        </View>

        {isDemo && (
          <View style={s.demoBanner}>
            <Text style={s.demoText}>🛠 Демо-режим — бэкенд недоступен</Text>
          </View>
        )}

        {/* Баланс */}
        <View style={s.balanceCard}>
          <Text style={s.balanceLabel}>Доступно к выводу</Text>
          <Text style={s.balanceAmount}>{formatAmount(balance.amount)}</Text>
          {balance.pending > 0 && (
            <Text style={s.balancePending}>+ {formatAmount(balance.pending)} ожидает подтверждения</Text>
          )}
        </View>

        {/* Активное задание */}
        <Text style={s.sectionTitle}>Текущее задание</Text>
        {activeTask ? (
          <TouchableOpacity
            style={s.activeTask}
            onPress={() => navigation.navigate('Tasks', {
              screen: 'TaskDetail',
              params: { task: activeTask },
            })}
          >
            <View style={s.activeTaskHeader}>
              <Text style={s.activeTaskTitle}>{activeTask.title}</Text>
              <View style={s.badge}>
                <Text style={s.badgeText}>В работе</Text>
              </View>
            </View>
            <Text style={s.activeTaskStore}>🏪 {activeTask.store}</Text>
            <Text style={s.activeTaskAddr}>📍 {activeTask.address}</Text>
            <View style={s.activeTaskFooter}>
              <Text style={s.activeTaskAmount}>{formatAmount(activeTask.amount)}</Text>
              <Text style={s.activeTaskLink}>Сдать работу →</Text>
            </View>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={s.noTask}
            onPress={() => navigation.navigate('Tasks', { screen: 'TasksList' })}
          >
            <Text style={s.noTaskIcon}>📋</Text>
            <Text style={s.noTaskText}>У вас нет активных заданий</Text>
            <Text style={s.noTaskLink}>Открыть биржу заданий →</Text>
          </TouchableOpacity>
        )}

        {/* Последние выплаты */}
        <Text style={s.sectionTitle}>Последние выплаты</Text>
        {recentPayments.map((p) => (
          <View key={p.id} style={s.payRow}>
            <View style={s.payInfo}>
              <Text style={s.payTitle}>{p.title}</Text>
              <Text style={s.payDate}>{p.date}</Text>
            </View>
            <Text style={s.payAmount}>+{formatAmount(p.amount)}</Text>
          </View>
        ))}

        {/* Быстрые действия */}
        <Text style={s.sectionTitle}>Быстрые действия</Text>
        <View style={s.quickRow}>
          <TouchableOpacity style={s.quickBtn} onPress={() => navigation.navigate('Tasks', { screen: 'TasksList' })}>
            <Text style={s.quickIcon}>🔍</Text>
            <Text style={s.quickLabel}>Биржа{'\n'}заданий</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.quickBtn} onPress={() => navigation.navigate('Wallet')}>
            <Text style={s.quickIcon}>💸</Text>
            <Text style={s.quickLabel}>История{'\n'}выплат</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.quickBtn} onPress={() => navigation.navigate('Profile')}>
            <Text style={s.quickIcon}>📄</Text>
            <Text style={s.quickLabel}>Мои{'\n'}документы</Text>
          </TouchableOpacity>
        </View>

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:   { flex: 1, backgroundColor: '#f0f2f5' },
  scroll: { flex: 1 },

  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: KARI, paddingHorizontal: 20, paddingVertical: 20,
  },
  greeting:    { fontSize: 20, fontWeight: '800', color: '#fff' },
  subGreeting: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  avatar: {
    width: 42, height: 42, borderRadius: 21,
    backgroundColor: 'rgba(255,255,255,0.25)',
    justifyContent: 'center', alignItems: 'center',
  },
  avatarText: { fontSize: 18, fontWeight: '700', color: '#fff' },

  demoBanner: {
    backgroundColor: '#fff3cd', paddingVertical: 8, paddingHorizontal: 16,
    alignItems: 'center',
  },
  demoText: { fontSize: 12, color: '#856404', fontWeight: '600' },

  balanceCard: {
    backgroundColor: DARK, margin: 16, borderRadius: 16,
    padding: 20, alignItems: 'center',
  },
  balanceLabel:   { fontSize: 13, color: 'rgba(255,255,255,0.6)', marginBottom: 4 },
  balanceAmount:  { fontSize: 36, fontWeight: '900', color: '#fff' },
  balancePending: { fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 4 },

  sectionTitle: {
    fontSize: 15, fontWeight: '700', color: DARK,
    marginHorizontal: 16, marginBottom: 8, marginTop: 4,
  },

  activeTask: {
    backgroundColor: '#fff', marginHorizontal: 16, borderRadius: 14,
    padding: 16, marginBottom: 16,
    borderLeftWidth: 4, borderLeftColor: GREEN,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 8, elevation: 3,
  },
  activeTaskHeader:  { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 },
  activeTaskTitle:   { fontSize: 16, fontWeight: '700', color: DARK, flex: 1, marginRight: 8 },
  badge:             { backgroundColor: GREEN, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  badgeText:         { fontSize: 11, color: '#fff', fontWeight: '600' },
  activeTaskStore:   { fontSize: 13, color: '#555', marginBottom: 2 },
  activeTaskAddr:    { fontSize: 12, color: '#888', marginBottom: 12 },
  activeTaskFooter:  { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  activeTaskAmount:  { fontSize: 20, fontWeight: '800', color: KARI },
  activeTaskLink:    { fontSize: 13, color: KARI, fontWeight: '600' },

  noTask: {
    backgroundColor: '#fff', marginHorizontal: 16, borderRadius: 14,
    padding: 24, alignItems: 'center', marginBottom: 16,
    borderWidth: 2, borderColor: '#f0f0f0', borderStyle: 'dashed',
  },
  noTaskIcon: { fontSize: 36, marginBottom: 8 },
  noTaskText: { fontSize: 15, color: '#888', marginBottom: 8 },
  noTaskLink: { fontSize: 14, color: KARI, fontWeight: '700' },

  payRow: {
    backgroundColor: '#fff', marginHorizontal: 16, borderRadius: 12,
    padding: 14, marginBottom: 8,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  payInfo:   { flex: 1, marginRight: 12 },
  payTitle:  { fontSize: 14, fontWeight: '600', color: DARK },
  payDate:   { fontSize: 12, color: '#888', marginTop: 2 },
  payAmount: { fontSize: 16, fontWeight: '700', color: GREEN },

  quickRow: {
    flexDirection: 'row', marginHorizontal: 16, gap: 10, marginBottom: 8,
  },
  quickBtn: {
    flex: 1, backgroundColor: '#fff', borderRadius: 14,
    padding: 16, alignItems: 'center',
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 6, elevation: 2,
  },
  quickIcon:  { fontSize: 28, marginBottom: 6 },
  quickLabel: { fontSize: 12, color: DARK, fontWeight: '600', textAlign: 'center', lineHeight: 16 },
});
