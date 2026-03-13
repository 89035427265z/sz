// =============================================================================
// KARI.Самозанятые — Экран блокировки стоп-листа
// Файл: src/screens/StopListBlockedScreen.js
// =============================================================================
//
// Показывается когда исполнитель попытался взять задание KARI,
// но его ИНН найден в стоп-листе (бывший сотрудник или штраф ФНС).
//
// Экран объясняет причину и предлагает два пути:
//   1) Оформиться в штат KARI — открывает Modal с инструкцией и контактами HR
//   2) Заказы партнёров       — переходит на биржу с внешними заданиями
//
// Данные приходят из params (navigate('StopListBlocked', { stopData }))
// =============================================================================

import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, Modal, Linking, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

// ─── Константы бренда ────────────────────────────────────────────────────────
const KARI  = '#A01F72';
const DARK  = '#242D4A';
const RED   = '#dc2626';
const AMBER = '#d97706';
const GREEN = '#16a34a';

// ─── Данные HR-службы KARI ───────────────────────────────────────────────────
const HR_CONTACTS = {
  phone:    '8-800-200-52-56',   // Бесплатная линия KARI
  email:    'hr@kari.ru',
  website:  'https://kari.com/career',
};

// ─── Шаги трудоустройства ───────────────────────────────────────────────────
const EMPLOYMENT_STEPS = [
  {
    num:  '1',
    icon: '📞',
    text: `Позвоните на горячую линию HR:\n${HR_CONTACTS.phone}\n(бесплатно по России)`,
  },
  {
    num:  '2',
    icon: '📋',
    text: 'Сообщите, что хотите оформиться в штат. Назовите ваше ФИО и ИНН.',
  },
  {
    num:  '3',
    icon: '🗓️',
    text: 'HR-менеджер согласует с вами удобное время для собеседования.',
  },
  {
    num:  '4',
    icon: '📄',
    text: 'Подпишите трудовой договор. С этого момента работаете в штате KARI с полным соцпакетом.',
  },
];


// =============================================================================
// Тексты причин — что видит исполнитель
// =============================================================================
const REASON_DATA = {
  former_employee: {
    icon:      '⏳',
    iconColor: AMBER,
    title:     'Ограничение по закону 422-ФЗ',
    subtitle:  'Бывший сотрудник KARI',
    body:      'По статье 6 Федерального закона № 422-ФЗ вы не можете выполнять задания как самозанятый для компании, в которой работали по трудовому договору в течение последних 2 лет.\n\nЭто требование Федеральной налоговой службы. KARI обязан его соблюдать, чтобы не нарушать налоговое законодательство.',
    helpNote:  'Ограничение снимается автоматически через 2 года после даты увольнения.',
  },
  fns_fine: {
    icon:      '⚠️',
    iconColor: RED,
    title:     'Нарушение по данным ФНС',
    subtitle:  'По вашему ИНН зафиксированы нарушения',
    body:      'По данным Федеральной налоговой службы по вашему ИНН зафиксированы нарушения, которые препятствуют выдаче заданий.\n\nДля уточнения подробностей обратитесь в HR-службу KARI.',
    helpNote:  'После урегулирования вопроса с ФНС HR-служба снимет ограничение.',
  },
  manual: {
    icon:      '🔒',
    iconColor: DARK,
    title:     'Временная блокировка',
    subtitle:  'Установлена HR-службой KARI',
    body:      'Выдача заданий временно приостановлена HR-службой KARI. Причина уточняется.',
    helpNote:  'Обратитесь в HR-службу для уточнения причины и сроков снятия ограничения.',
  },
};

const DEFAULT_REASON = REASON_DATA.manual;


// =============================================================================
// ГЛАВНЫЙ ЭКРАН
// =============================================================================
export default function StopListBlockedScreen({ route, navigation }) {
  // Данные из take_task 403 ответа
  const stopData = route.params?.stopData || {};
  const {
    reason       = 'manual',
    blocked_until,
    reason_label,
  } = stopData;

  const data = REASON_DATA[reason] || DEFAULT_REASON;

  // Состояния
  const [hrModalVisible,  setHrModal]  = useState(false);
  const [infoExpanded,    setInfoExp]  = useState(false);

  // ── Форматируем дату разблокировки ──────────────────────────────────────
  const formatDate = (isoStr) => {
    if (!isoStr) return null;
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return isoStr;
    }
  };

  // ── Открываем телефон или email ──────────────────────────────────────────
  const callHR = () => {
    const tel = `tel:${HR_CONTACTS.phone.replace(/[^0-9+]/g, '')}`;
    Linking.canOpenURL(tel).then(ok => {
      if (ok) Linking.openURL(tel);
    });
  };

  const emailHR = () => {
    Linking.openURL(`mailto:${HR_CONTACTS.email}?subject=Стоп-лист KARI — запрос`);
  };

  const openCareers = () => {
    Linking.openURL(HR_CONTACTS.website);
  };

  // ── Переходим на биржу внешних партнёров ────────────────────────────────
  const goToPartnerTasks = () => {
    navigation.navigate('Main', {
      screen: 'Tasks',
      params: {
        screen:      'TasksList',
        params:      { partnerOnly: true },
      },
    });
  };

  // ── Назад на главную ─────────────────────────────────────────────────────
  const goHome = () => {
    navigation.navigate('Main', { screen: 'Home' });
  };

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.container}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Шапка с большой иконкой ──────────────────────────────────── */}
        <View style={s.heroBlock}>
          <View style={[s.iconCircle, { borderColor: data.iconColor }]}>
            <Text style={s.heroIcon}>{data.icon}</Text>
          </View>
          <Text style={s.heroTitle}>{data.title}</Text>
          <Text style={s.heroSub}>{data.subtitle}</Text>

          {/* Дата снятия блокировки */}
          {blocked_until && (
            <View style={s.dateBadge}>
              <Text style={s.dateBadgeText}>
                🗓 Ограничение действует до{' '}
                <Text style={s.dateBadgeBold}>{formatDate(blocked_until)}</Text>
              </Text>
            </View>
          )}
        </View>

        {/* ── Объяснение причины ───────────────────────────────────────── */}
        <View style={s.card}>
          <TouchableOpacity
            style={s.cardHeader}
            onPress={() => setInfoExp(!infoExpanded)}
            activeOpacity={0.7}
          >
            <Text style={s.cardHeaderText}>Почему это происходит?</Text>
            <Text style={s.chevron}>{infoExpanded ? '▲' : '▼'}</Text>
          </TouchableOpacity>

          {infoExpanded && (
            <View style={s.cardBody}>
              <Text style={s.cardText}>{data.body}</Text>
              <View style={s.helpNote}>
                <Text style={s.helpNoteText}>💡 {data.helpNote}</Text>
              </View>
            </View>
          )}
        </View>

        {/* ── ВАРИАНТ 1: Оформиться в штат ──────────────────────────────── */}
        <View style={s.optionCard}>
          <View style={s.optionHeader}>
            <View style={[s.optionNum, { backgroundColor: KARI }]}>
              <Text style={s.optionNumText}>1</Text>
            </View>
            <View style={s.optionHeaderText}>
              <Text style={s.optionTitle}>Оформиться в штат KARI</Text>
              <Text style={s.optionDesc}>
                Стабильная работа, соцпакет, оплачиваемый отпуск
              </Text>
            </View>
          </View>

          {/* Преимущества штатной работы */}
          <View style={s.benefitsList}>
            {[
              '📅  Стабильный график и оплата',
              '🏥  Медицинская страховка (ДМС)',
              '🏖  Оплачиваемый отпуск 28 дней',
              '📈  Карьерный рост внутри KARI',
              '🛍  Скидка на обувь KARI до 40%',
            ].map((b, i) => (
              <Text key={i} style={s.benefit}>{b}</Text>
            ))}
          </View>

          <TouchableOpacity
            style={[s.btn, { backgroundColor: KARI }]}
            onPress={() => setHrModal(true)}
            activeOpacity={0.85}
          >
            <Text style={s.btnText}>📞 Как оформиться — инструкция</Text>
          </TouchableOpacity>
        </View>

        {/* ── ВАРИАНТ 2: Заказы партнёров ──────────────────────────────── */}
        <View style={s.optionCard}>
          <View style={s.optionHeader}>
            <View style={[s.optionNum, { backgroundColor: '#2563eb' }]}>
              <Text style={s.optionNumText}>2</Text>
            </View>
            <View style={s.optionHeaderText}>
              <Text style={s.optionTitle}>Заказы внешних партнёров</Text>
              <Text style={s.optionDesc}>
                Задания от других компаний — доступны прямо сейчас
              </Text>
            </View>
          </View>

          <Text style={s.partnerInfo}>
            На нашей бирже есть задания от партнёров KARI — других розничных
            сетей и компаний. Закон 422-ФЗ не запрещает вам работать с ними
            как самозанятому.
          </Text>

          <View style={s.benefitsList}>
            {[
              '✅  Доступно прямо сейчас',
              '💰  Оплата та же — без задержек',
              '📍  Работа в тех же магазинах и локациях',
            ].map((b, i) => (
              <Text key={i} style={s.benefit}>{b}</Text>
            ))}
          </View>

          <TouchableOpacity
            style={[s.btn, { backgroundColor: '#2563eb' }]}
            onPress={goToPartnerTasks}
            activeOpacity={0.85}
          >
            <Text style={s.btnText}>🔍 Смотреть заказы партнёров</Text>
          </TouchableOpacity>
        </View>

        {/* ── Кнопка назад ─────────────────────────────────────────────── */}
        <TouchableOpacity style={s.backBtn} onPress={goHome} activeOpacity={0.7}>
          <Text style={s.backBtnText}>← Вернуться на главную</Text>
        </TouchableOpacity>

      </ScrollView>

      {/* ================================================================== */}
      {/* МОДАЛЬНОЕ ОКНО: Инструкция по трудоустройству                       */}
      {/* ================================================================== */}
      <Modal
        visible={hrModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setHrModal(false)}
      >
        <View style={s.modalOverlay}>
          <View style={s.modalSheet}>
            {/* Ручка */}
            <View style={s.modalHandle} />

            <ScrollView showsVerticalScrollIndicator={false}>
              {/* Заголовок */}
              <Text style={s.modalTitle}>Как оформиться в штат KARI</Text>
              <Text style={s.modalSub}>
                4 шага — и вы в команде крупнейшей обувной сети России
              </Text>

              {/* Шаги */}
              {EMPLOYMENT_STEPS.map((step, i) => (
                <View key={i} style={s.stepRow}>
                  <View style={s.stepNumCircle}>
                    <Text style={s.stepNumText}>{step.num}</Text>
                  </View>
                  <View style={s.stepContent}>
                    <Text style={s.stepIcon}>{step.icon}</Text>
                    <Text style={s.stepText}>{step.text}</Text>
                  </View>
                </View>
              ))}

              {/* Контакты */}
              <View style={s.contactsBlock}>
                <Text style={s.contactsTitle}>Контакты HR-службы</Text>

                <TouchableOpacity style={s.contactBtn} onPress={callHR} activeOpacity={0.8}>
                  <Text style={s.contactBtnIcon}>📞</Text>
                  <View>
                    <Text style={s.contactBtnLabel}>Телефон (бесплатно)</Text>
                    <Text style={s.contactBtnValue}>{HR_CONTACTS.phone}</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity style={s.contactBtn} onPress={emailHR} activeOpacity={0.8}>
                  <Text style={s.contactBtnIcon}>✉️</Text>
                  <View>
                    <Text style={s.contactBtnLabel}>Email</Text>
                    <Text style={s.contactBtnValue}>{HR_CONTACTS.email}</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity style={s.contactBtn} onPress={openCareers} activeOpacity={0.8}>
                  <Text style={s.contactBtnIcon}>🌐</Text>
                  <View>
                    <Text style={s.contactBtnLabel}>Все вакансии KARI</Text>
                    <Text style={s.contactBtnValue}>kari.com/career</Text>
                  </View>
                </TouchableOpacity>
              </View>

              {/* Кнопка закрыть */}
              <TouchableOpacity
                style={[s.btn, { backgroundColor: KARI, marginBottom: 8 }]}
                onPress={callHR}
                activeOpacity={0.85}
              >
                <Text style={s.btnText}>📞 Позвонить в HR прямо сейчас</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={s.modalCloseBtn}
                onPress={() => setHrModal(false)}
                activeOpacity={0.7}
              >
                <Text style={s.modalCloseTxt}>Закрыть</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}


// =============================================================================
// СТИЛИ
// =============================================================================
const s = StyleSheet.create({
  safe:   { flex: 1, backgroundColor: '#f4f5f8' },
  scroll: { flex: 1 },
  container: { padding: 20, paddingBottom: 40 },

  // ── Герой ────────────────────────────────────────────────────────────────
  heroBlock: {
    alignItems: 'center',
    paddingVertical: 28,
    paddingHorizontal: 20,
  },
  iconCircle: {
    width: 96, height: 96,
    borderRadius: 48,
    borderWidth: 3,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 6,
  },
  heroIcon:  { fontSize: 48 },
  heroTitle: {
    fontSize: 20, fontWeight: '800',
    color: DARK, textAlign: 'center',
    marginBottom: 6,
  },
  heroSub: {
    fontSize: 14, color: '#666',
    textAlign: 'center',
    marginBottom: 14,
  },
  dateBadge: {
    backgroundColor: '#fef3c7',
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: '#fcd34d',
  },
  dateBadgeText:  { fontSize: 13, color: '#92400e', textAlign: 'center' },
  dateBadgeBold:  { fontWeight: '800' },

  // ── Карточка объяснения ──────────────────────────────────────────────────
  card: {
    backgroundColor: '#fff',
    borderRadius: 14,
    marginBottom: 14,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  cardHeaderText: { fontSize: 15, fontWeight: '700', color: DARK, flex: 1 },
  chevron:        { fontSize: 13, color: '#999', marginLeft: 8 },
  cardBody: { paddingHorizontal: 16, paddingBottom: 16 },
  cardText: { fontSize: 14, color: '#444', lineHeight: 20 },
  helpNote: {
    marginTop: 12,
    backgroundColor: '#eff6ff',
    borderRadius: 8,
    padding: 10,
    borderLeftWidth: 3,
    borderLeftColor: '#3b82f6',
  },
  helpNoteText: { fontSize: 13, color: '#1e40af', lineHeight: 18 },

  // ── Карточки вариантов ───────────────────────────────────────────────────
  optionCard: {
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 18,
    marginBottom: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 6,
    elevation: 3,
  },
  optionHeader: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 14 },
  optionNum:    {
    width: 32, height: 32, borderRadius: 16,
    alignItems: 'center', justifyContent: 'center',
    marginRight: 12, marginTop: 2,
  },
  optionNumText: { color: '#fff', fontWeight: '900', fontSize: 16 },
  optionHeaderText: { flex: 1 },
  optionTitle: { fontSize: 16, fontWeight: '800', color: DARK, marginBottom: 3 },
  optionDesc:  { fontSize: 13, color: '#666' },

  benefitsList: { marginBottom: 16 },
  benefit: {
    fontSize: 13, color: '#444',
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: '#f5f5f5',
  },
  partnerInfo: {
    fontSize: 13, color: '#555',
    lineHeight: 19,
    backgroundColor: '#eff6ff',
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },

  // ── Кнопки ───────────────────────────────────────────────────────────────
  btn: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 15 },

  backBtn: { alignItems: 'center', marginTop: 10, paddingVertical: 12 },
  backBtnText: { fontSize: 14, color: '#999', fontWeight: '600' },

  // ── Модальное окно HR ──────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    maxHeight: '92%',
  },
  modalHandle: {
    width: 40, height: 4,
    backgroundColor: '#e0e0e0',
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 20, fontWeight: '900',
    color: DARK, textAlign: 'center',
    marginBottom: 6,
  },
  modalSub: {
    fontSize: 14, color: '#666',
    textAlign: 'center',
    marginBottom: 24,
  },

  // ── Шаги трудоустройства ──────────────────────────────────────────────
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 18,
  },
  stepNumCircle: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: KARI,
    alignItems: 'center', justifyContent: 'center',
    marginRight: 14,
    marginTop: 2,
    flexShrink: 0,
  },
  stepNumText: { color: '#fff', fontWeight: '900', fontSize: 15 },
  stepContent:  { flex: 1 },
  stepIcon:     { fontSize: 18, marginBottom: 4 },
  stepText:     { fontSize: 14, color: '#444', lineHeight: 20 },

  // ── Контакты ──────────────────────────────────────────────────────────
  contactsBlock: {
    backgroundColor: '#f8f9fb',
    borderRadius: 12,
    padding: 16,
    marginVertical: 16,
  },
  contactsTitle: {
    fontSize: 15, fontWeight: '800',
    color: DARK, marginBottom: 12,
  },
  contactBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#eeeeee',
  },
  contactBtnIcon:  { fontSize: 22, marginRight: 14 },
  contactBtnLabel: { fontSize: 11, color: '#888', marginBottom: 2 },
  contactBtnValue: { fontSize: 14, fontWeight: '700', color: DARK },

  // ── Закрыть модалку ───────────────────────────────────────────────────
  modalCloseBtn: { alignItems: 'center', paddingVertical: 14, marginBottom: 8 },
  modalCloseTxt: { fontSize: 15, color: '#999', fontWeight: '600' },
});
