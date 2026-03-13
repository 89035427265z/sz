// Экран профиля: данные исполнителя, статус ФНС, настройки
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, Alert, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../hooks/useAuth';

const KARI  = '#A01F72';
const DARK  = '#242D4A';
const GREEN = '#27ae60';
const WARN  = '#e67e22';

export default function ProfileScreen() {
  const { user, logout } = useAuth();

  // Для демо — дополняем данные пользователя
  const profile = {
    full_name:   user?.full_name  || 'Иванов Иван Иванович',
    inn:         user?.inn        || '381234560001',
    phone:       user?.phone      || '+7 914 123-45-01',
    fns_status:  user?.fns_status || 'active',
    bank_card:   user?.bank_card  || '**** **** **** 4567',
    registered:  user?.registered || '01.03.2026',
    rating:      user?.rating     || 4.8,
    tasks_done:  user?.tasks_done || 24,
  };

  const [notifPayments, setNotifPayments] = useState(true);
  const [notifNewTasks, setNotifNewTasks] = useState(true);
  const [notifDocs,     setNotifDocs]     = useState(true);

  const handleLogout = () => {
    Alert.alert(
      'Выход',
      'Вы уверены, что хотите выйти из аккаунта?',
      [
        { text: 'Отмена', style: 'cancel' },
        { text: 'Выйти', style: 'destructive', onPress: logout },
      ]
    );
  };

  const initials = profile.full_name.split(' ').slice(0, 2).map(w => w[0]).join('');
  const fnsOk = profile.fns_status === 'active';

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <ScrollView style={s.scroll}>
        {/* Шапка профиля */}
        <View style={s.header}>
          <View style={s.avatar}>
            <Text style={s.avatarText}>{initials}</Text>
          </View>
          <Text style={s.name}>{profile.full_name}</Text>
          <Text style={s.phone}>{profile.phone}</Text>
          <View style={[s.fnsChip, { backgroundColor: fnsOk ? '#e8f5e9' : '#ffebee' }]}>
            <Text style={[s.fnsChipText, { color: fnsOk ? GREEN : '#e53935' }]}>
              {fnsOk ? '✅ Самозанятый — активен' : '⛔ Статус ФНС не подтверждён'}
            </Text>
          </View>
        </View>

        {/* Статистика */}
        <View style={s.statsRow}>
          <View style={s.statBox}>
            <Text style={s.statVal}>{profile.tasks_done}</Text>
            <Text style={s.statLbl}>Заданий</Text>
          </View>
          <View style={s.statDivider} />
          <View style={s.statBox}>
            <Text style={s.statVal}>⭐ {profile.rating}</Text>
            <Text style={s.statLbl}>Рейтинг</Text>
          </View>
          <View style={s.statDivider} />
          <View style={s.statBox}>
            <Text style={s.statVal}>c {profile.registered}</Text>
            <Text style={s.statLbl}>В системе</Text>
          </View>
        </View>

        {/* Личные данные */}
        <Text style={s.groupTitle}>Личные данные</Text>
        <View style={s.card}>
          <InfoRow icon="🪪" label="ИНН" value={profile.inn} />
          <InfoRow icon="📱" label="Телефон" value={profile.phone} />
          <InfoRow icon="💳" label="Карта для выплат" value={profile.bank_card} />
        </View>

        {/* Статус самозанятого */}
        <Text style={s.groupTitle}>Статус самозанятого (ФНС)</Text>
        <View style={[s.card, { borderLeftWidth: 4, borderLeftColor: fnsOk ? GREEN : '#e53935' }]}>
          <View style={s.fnsRow}>
            <Text style={s.fnsIcon}>{fnsOk ? '✅' : '⛔'}</Text>
            <View style={s.fnsInfo}>
              <Text style={s.fnsTitle}>
                {fnsOk ? 'Активный плательщик НПД' : 'Статус не подтверждён'}
              </Text>
              <Text style={s.fnsDesc}>
                {fnsOk
                  ? 'Проверка выполняется ежедневно в 07:00. Статус в норме.'
                  : 'Зарегистрируйтесь в приложении «Мой налог» и обновите статус.'}
              </Text>
            </View>
          </View>
          {!fnsOk && (
            <TouchableOpacity style={s.refreshFnsBtn}>
              <Text style={s.refreshFnsBtnText}>🔄 Обновить статус</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Уведомления */}
        <Text style={s.groupTitle}>Уведомления</Text>
        <View style={s.card}>
          <NotifRow label="Новые задания в моём регионе" value={notifNewTasks} onChange={setNotifNewTasks} />
          <NotifRow label="Выплаты и операции"           value={notifPayments} onChange={setNotifPayments} />
          <NotifRow label="Документы для подписания"     value={notifDocs}     onChange={setNotifDocs} />
        </View>

        {/* Поддержка */}
        <Text style={s.groupTitle}>Поддержка</Text>
        <View style={s.card}>
          <TouchableOpacity style={s.menuRow} onPress={() => Alert.alert('Поддержка', 'Telegram: @kari_support')}>
            <Text style={s.menuIcon}>💬</Text>
            <Text style={s.menuLabel}>Написать в поддержку</Text>
            <Text style={s.menuArrow}>›</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.menuRow}>
            <Text style={s.menuIcon}>📖</Text>
            <Text style={s.menuLabel}>Как работает KARI Самозанятые</Text>
            <Text style={s.menuArrow}>›</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.menuRow}>
            <Text style={s.menuIcon}>⚖️</Text>
            <Text style={s.menuLabel}>Оферта и условия сотрудничества</Text>
            <Text style={s.menuArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* Версия и выход */}
        <Text style={s.version}>KARI Самозанятые · v1.0.0 · Пилот Апрель 2026</Text>

        <TouchableOpacity style={s.logoutBtn} onPress={handleLogout}>
          <Text style={s.logoutText}>Выйти из аккаунта</Text>
        </TouchableOpacity>

        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// Строка с информацией
function InfoRow({ icon, label, value }) {
  return (
    <View style={s.infoRow}>
      <Text style={s.infoIcon}>{icon}</Text>
      <View style={s.infoContent}>
        <Text style={s.infoLabel}>{label}</Text>
        <Text style={s.infoValue}>{value}</Text>
      </View>
    </View>
  );
}

// Строка переключателя уведомлений
function NotifRow({ label, value, onChange }) {
  return (
    <View style={s.notifRow}>
      <Text style={s.notifLabel}>{label}</Text>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: '#e0e0e0', true: KARI + '60' }}
        thumbColor={value ? KARI : '#f5f5f5'}
      />
    </View>
  );
}

const s = StyleSheet.create({
  safe:   { flex: 1, backgroundColor: '#f0f2f5' },
  scroll: { flex: 1 },

  header: {
    backgroundColor: KARI, paddingTop: 24, paddingBottom: 28,
    alignItems: 'center', gap: 8,
  },
  avatar: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: 'rgba(255,255,255,0.25)',
    justifyContent: 'center', alignItems: 'center', marginBottom: 4,
  },
  avatarText: { fontSize: 28, fontWeight: '800', color: '#fff' },
  name:       { fontSize: 20, fontWeight: '800', color: '#fff' },
  phone:      { fontSize: 14, color: 'rgba(255,255,255,0.7)' },
  fnsChip: { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 5 },
  fnsChipText: { fontSize: 13, fontWeight: '700' },

  statsRow: {
    backgroundColor: '#fff', flexDirection: 'row',
    paddingVertical: 16, marginBottom: 0,
    borderBottomWidth: 1, borderBottomColor: '#f0f0f0',
  },
  statBox:     { flex: 1, alignItems: 'center' },
  statDivider: { width: 1, backgroundColor: '#f0f0f0' },
  statVal:     { fontSize: 16, fontWeight: '800', color: DARK },
  statLbl:     { fontSize: 12, color: '#888', marginTop: 3 },

  groupTitle: {
    fontSize: 13, fontWeight: '700', color: '#888',
    marginHorizontal: 16, marginTop: 20, marginBottom: 8,
    textTransform: 'uppercase', letterSpacing: 0.5,
  },

  card: {
    backgroundColor: '#fff', marginHorizontal: 16, borderRadius: 14,
    overflow: 'hidden',
  },

  infoRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 14,
    paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: '#f5f5f5',
  },
  infoIcon:    { fontSize: 22, marginRight: 12 },
  infoContent: { flex: 1 },
  infoLabel:   { fontSize: 12, color: '#888', marginBottom: 2 },
  infoValue:   { fontSize: 15, fontWeight: '600', color: DARK },

  fnsRow: { flexDirection: 'row', padding: 16, gap: 12 },
  fnsIcon: { fontSize: 32 },
  fnsInfo: { flex: 1 },
  fnsTitle:{ fontSize: 15, fontWeight: '700', color: DARK },
  fnsDesc: { fontSize: 13, color: '#666', marginTop: 4, lineHeight: 18 },
  refreshFnsBtn: {
    marginHorizontal: 16, marginBottom: 14, backgroundColor: '#f0f0f0',
    borderRadius: 10, paddingVertical: 10, alignItems: 'center',
  },
  refreshFnsBtnText: { fontSize: 14, fontWeight: '600', color: DARK },

  notifRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingVertical: 12, paddingHorizontal: 16,
    borderBottomWidth: 1, borderBottomColor: '#f5f5f5',
  },
  notifLabel: { fontSize: 14, color: DARK, flex: 1, marginRight: 12 },

  menuRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 14,
    paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: '#f5f5f5',
  },
  menuIcon:  { fontSize: 20, marginRight: 12 },
  menuLabel: { flex: 1, fontSize: 14, color: DARK },
  menuArrow: { fontSize: 20, color: '#ccc' },

  version:   { textAlign: 'center', fontSize: 11, color: '#aaa', marginTop: 20, marginBottom: 8 },

  logoutBtn: {
    marginHorizontal: 16, marginBottom: 8, borderWidth: 1.5, borderColor: '#ffcccc',
    borderRadius: 14, paddingVertical: 14, alignItems: 'center',
    backgroundColor: '#fff5f5',
  },
  logoutText: { fontSize: 15, fontWeight: '700', color: '#e74c3c' },
});
