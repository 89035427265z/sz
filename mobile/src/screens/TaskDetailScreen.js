// Карточка задания: полная информация, кнопка "Взять задание" / "Сдать работу"
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, Alert, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { acceptTask, declineTask } from '../api/client';

const KARI  = '#A01F72';
const DARK  = '#242D4A';
const GREEN = '#27ae60';
const RED   = '#e74c3c';

export default function TaskDetailScreen({ route, navigation }) {
  // Задание передаётся из TasksScreen или HomeScreen через params
  const { task: initialTask } = route.params;
  const [task, setTask]     = useState(initialTask);
  const [loading, setLoad]  = useState(false);

  const fmt = (n) => n?.toLocaleString('ru-RU') + ' ₽';

  const isFull = task.executors_taken >= task.executors_needed;
  const canAccept  = task.status === 'available' && !isFull;
  const canSubmit  = task.status === 'in_progress';
  const canDecline = task.status === 'in_progress';

  // Взять задание
  const handleAccept = () => {
    Alert.alert(
      'Взять задание',
      `Подтвердите, что берёте задание:\n«${task.title}»\nв ${task.store}\nза ${fmt(task.amount)}`,
      [
        { text: 'Отмена', style: 'cancel' },
        {
          text: 'Взять',
          onPress: async () => {
            setLoad(true);
            try {
              await acceptTask(task.id);
              setTask(t => ({ ...t, status: 'in_progress' }));
              Alert.alert('✅ Задание взято!', 'Теперь выполните работу и сдайте фотоотчёт.');
            } catch (e) {
              // ── Проверяем: стоп-лист (403 с code STOP_LIST_BLOCKED) ──────
              // Бэкенд возвращает detail: { code, reason, message, blocked_until }
              const detail = e?.response?.data?.detail;
              if (detail && typeof detail === 'object' && detail.code === 'STOP_LIST_BLOCKED') {
                // Переходим на экран StopListBlocked с данными причины
                navigation.navigate('StopListBlocked', { stopData: detail });
                return; // не показываем обычный Alert
              }

              // ── Другие ошибки 403 ────────────────────────────────────────
              const errMsg = (typeof detail === 'string' ? detail : null)
                || e?.message
                || 'Не удалось взять задание. Попробуйте ещё раз.';
              Alert.alert('Ошибка', errMsg);
            } finally {
              setLoad(false);
            }
          },
        },
      ]
    );
  };

  // Отказаться от задания
  const handleDecline = () => {
    Alert.alert(
      'Отказаться от задания',
      'Вы уверены? Задание вернётся в биржу, а ваш рейтинг может снизиться.',
      [
        { text: 'Нет', style: 'cancel' },
        {
          text: 'Отказаться',
          style: 'destructive',
          onPress: async () => {
            setLoad(true);
            try {
              await declineTask(task.id);
            } catch {}
            setTask(t => ({ ...t, status: 'available', executors_taken: Math.max(0, t.executors_taken - 1) }));
            navigation.goBack();
            setLoad(false);
          },
        },
      ]
    );
  };

  // Перейти к сдаче работы
  const handleSubmit = () => {
    navigation.navigate('SubmitTask', { task });
  };

  // Цвет статуса
  const statusColor = {
    available: KARI,
    in_progress: GREEN,
    done: '#888',
    cancelled: RED,
  }[task.status] || KARI;

  const statusLabel = {
    available: '🟣 Доступно',
    in_progress: '🟢 В работе',
    done: '✅ Завершено',
    cancelled: '⛔ Отменено',
  }[task.status] || task.status;

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      {/* Шапка с кнопкой назад */}
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => navigation.goBack()}>
          <Text style={s.backArrow}>←</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>Задание</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={s.scroll} contentContainerStyle={s.content}>

        {/* Сумма и статус */}
        <View style={s.heroCard}>
          <Text style={s.heroAmount}>{fmt(task.amount)}</Text>
          <View style={[s.statusBadge, { backgroundColor: statusColor + '20' }]}>
            <Text style={[s.statusText, { color: statusColor }]}>{statusLabel}</Text>
          </View>
        </View>

        {/* Заголовок задания */}
        <View style={s.section}>
          <Text style={s.taskTitle}>{task.title}</Text>
          <View style={s.tagRow}>
            {task.category && (
              <View style={s.tag}><Text style={s.tagText}>📂 {task.category}</Text></View>
            )}
            <View style={s.tag}><Text style={s.tagText}>⏱ {task.duration_hours} ч.</Text></View>
          </View>
        </View>

        {/* Место */}
        <View style={s.infoCard}>
          <Text style={s.infoCardTitle}>📍 Место выполнения</Text>
          <Text style={s.infoRow}>🏪 {task.store}</Text>
          <Text style={s.infoRow}>📍 {task.address}</Text>
        </View>

        {/* Сроки */}
        <View style={s.infoCard}>
          <Text style={s.infoCardTitle}>📅 Сроки</Text>
          <Text style={s.infoRow}>Срок сдачи: {task.deadline}</Text>
          <Text style={s.infoRow}>Длительность: {task.duration_hours} часов</Text>
        </View>

        {/* Исполнители */}
        <View style={s.infoCard}>
          <Text style={s.infoCardTitle}>👥 Исполнители</Text>
          <View style={s.execRow}>
            <View style={s.execBar}>
              <View style={[
                s.execFill,
                {
                  width: `${Math.min(100, (task.executors_taken / task.executors_needed) * 100)}%`,
                  backgroundColor: isFull ? RED : GREEN,
                }
              ]} />
            </View>
            <Text style={s.execCount}>
              {task.executors_taken}/{task.executors_needed}
              {isFull ? ' — мест нет' : ' — есть места'}
            </Text>
          </View>
        </View>

        {/* Описание задания */}
        <View style={s.infoCard}>
          <Text style={s.infoCardTitle}>📝 Что нужно сделать</Text>
          <Text style={s.description}>
            {task.description || `Выполнить задание «${task.title}» в магазине ${task.store}.\n\nПосле выполнения сделать 1–3 фото результата с геометкой и отправить в приложении. Директор магазина проверит и подтвердит выполнение.`}
          </Text>
        </View>

        {/* Порядок выплаты */}
        <View style={s.payInfoCard}>
          <Text style={s.payInfoTitle}>💰 Порядок выплаты</Text>
          <Text style={s.payInfoText}>
            1. Вы выполняете работу и сдаёте фотоотчёт{'\n'}
            2. Директор магазина принимает работу{'\n'}
            3. Вы подписываете акт ПЭП через SMS{'\n'}
            4. Выплата поступает в течение 3 рабочих дней{'\n'}
            5. KARI компенсирует ваш налог 6% (НПД)
          </Text>
        </View>

        {/* Кнопки действий */}
        <View style={s.actions}>
          {canAccept && (
            <TouchableOpacity style={[s.btnPrimary, loading && s.btnOff]} onPress={handleAccept} disabled={loading}>
              {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnPrimaryText}>✅ Взять задание</Text>}
            </TouchableOpacity>
          )}

          {isFull && task.status === 'available' && (
            <View style={s.btnDisabledBox}>
              <Text style={s.btnDisabledText}>⛔ Все места заняты — нельзя взять</Text>
            </View>
          )}

          {canSubmit && (
            <TouchableOpacity style={s.btnGreen} onPress={handleSubmit}>
              <Text style={s.btnPrimaryText}>📸 Сдать работу</Text>
            </TouchableOpacity>
          )}

          {canDecline && (
            <TouchableOpacity style={s.btnOutline} onPress={handleDecline} disabled={loading}>
              <Text style={s.btnOutlineText}>Отказаться от задания</Text>
            </TouchableOpacity>
          )}
        </View>

        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:   { flex: 1, backgroundColor: '#f0f2f5' },
  header: {
    backgroundColor: KARI, paddingHorizontal: 16, paddingVertical: 14,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  backBtn:     { width: 40, height: 40, justifyContent: 'center' },
  backArrow:   { fontSize: 24, color: '#fff', fontWeight: '700' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#fff' },

  scroll:  { flex: 1 },
  content: { padding: 16, gap: 12 },

  heroCard: {
    backgroundColor: DARK, borderRadius: 16, padding: 24,
    alignItems: 'center', gap: 10,
  },
  heroAmount:   { fontSize: 42, fontWeight: '900', color: '#fff' },
  statusBadge:  { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 5 },
  statusText:   { fontSize: 14, fontWeight: '700' },

  section:   { backgroundColor: '#fff', borderRadius: 14, padding: 16 },
  taskTitle: { fontSize: 20, fontWeight: '800', color: DARK, marginBottom: 8 },
  tagRow:    { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  tag:       { backgroundColor: '#f0f0f0', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  tagText:   { fontSize: 12, fontWeight: '600', color: '#555' },

  infoCard:      { backgroundColor: '#fff', borderRadius: 14, padding: 16, gap: 6 },
  infoCardTitle: { fontSize: 14, fontWeight: '700', color: DARK, marginBottom: 4 },
  infoRow:       { fontSize: 14, color: '#555' },

  execRow: { gap: 8 },
  execBar: { height: 8, backgroundColor: '#f0f0f0', borderRadius: 4, overflow: 'hidden' },
  execFill:{ height: '100%', borderRadius: 4 },
  execCount: { fontSize: 13, color: '#555', fontWeight: '600' },

  description: { fontSize: 14, color: '#444', lineHeight: 22 },

  payInfoCard: {
    backgroundColor: '#f0f9ff', borderRadius: 14, padding: 16,
    borderLeftWidth: 4, borderLeftColor: '#3498db',
  },
  payInfoTitle: { fontSize: 14, fontWeight: '700', color: DARK, marginBottom: 8 },
  payInfoText:  { fontSize: 13, color: '#444', lineHeight: 22 },

  actions: { gap: 10 },
  btnPrimary: {
    backgroundColor: KARI, borderRadius: 14,
    paddingVertical: 16, alignItems: 'center',
  },
  btnGreen: {
    backgroundColor: GREEN, borderRadius: 14,
    paddingVertical: 16, alignItems: 'center',
  },
  btnOff:         { opacity: 0.6 },
  btnPrimaryText: { color: '#fff', fontSize: 16, fontWeight: '700' },

  btnOutline: {
    borderWidth: 2, borderColor: '#e0e0e0', borderRadius: 14,
    paddingVertical: 14, alignItems: 'center',
  },
  btnOutlineText: { fontSize: 15, fontWeight: '600', color: '#888' },

  btnDisabledBox: {
    backgroundColor: '#fff0f0', borderRadius: 14,
    paddingVertical: 14, alignItems: 'center',
  },
  btnDisabledText: { fontSize: 14, fontWeight: '600', color: RED },
});
