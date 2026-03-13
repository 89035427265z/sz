// Экран кошелька: баланс, история выплат, документы
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, RefreshControl, FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { getWallet, getDocuments, requestDocumentSign, confirmDocumentSign } from '../api/client';

const KARI  = '#A01F72';
const DARK  = '#242D4A';
const GREEN = '#27ae60';
const WARN  = '#e67e22';

// Демо-данные
const DEMO_WALLET = {
  balance:          12400,
  pending:          3700,
  total_earned:     89500,
  total_tasks:      24,
  income_this_year: 89500,
  income_limit:     2400000,
};

const DEMO_PAYMENTS = [
  { id: 'p1', task_title: 'Выкладка весенней коллекции', store: 'ТЦ «Мегас»',    amount: 2200, date: '28.03.2026', status: 'paid',    doc_number: 'АКТ-2026-000018' },
  { id: 'p2', task_title: 'Уборка зала после акции',     store: 'ТЦ «Карамель»', amount: 1500, date: '25.03.2026', status: 'paid',    doc_number: 'АКТ-2026-000015' },
  { id: 'p3', task_title: 'Инвентаризация склада',       store: 'ТЦ «Аквамолл»', amount: 3500, date: '20.03.2026', status: 'paid',    doc_number: 'АКТ-2026-000012' },
  { id: 'p4', task_title: 'Промо-акция: листовки',       store: 'ТЦ «Карамель»', amount: 900,  date: '15.03.2026', status: 'paid',    doc_number: 'АКТ-2026-000009' },
  { id: 'p5', task_title: 'Уборка торгового зала',       store: 'ТЦ «Карамель»', amount: 3700, date: 'ожидается', status: 'pending', doc_number: null },
];

const DEMO_DOCS = [
  { id: 'd1', number: 'ДГ-2026-000003',  type: 'contract', status: 'signed',        date: '01.03.2026', title: 'Договор ГПХ №3' },
  { id: 'd2', number: 'АКТ-2026-000018', type: 'act',      status: 'pending_sign',  date: '28.03.2026', title: 'Акт №18' },
  { id: 'd3', number: 'АКТ-2026-000015', type: 'act',      status: 'signed',        date: '25.03.2026', title: 'Акт №15' },
];

const STATUS_COLORS = {
  paid:         { bg: '#e8f5e9', text: GREEN,  label: '✅ Выплачено' },
  pending:      { bg: '#fff8e1', text: WARN,   label: '⏳ Ожидает' },
  signed:       { bg: '#e8f5e9', text: GREEN,  label: '✅ Подписан' },
  pending_sign: { bg: '#fff3cd', text: WARN,   label: '✍️ Нужна подпись' },
  cancelled:    { bg: '#ffebee', text: '#e53935', label: '⛔ Отменён' },
};

const TABS = [
  { key: 'payments', label: '💸 Выплаты' },
  { key: 'docs',     label: '📄 Документы' },
];

export default function WalletScreen() {
  const [wallet, setWallet]       = useState(DEMO_WALLET);
  const [payments, setPayments]   = useState(DEMO_PAYMENTS);
  const [docs, setDocs]           = useState(DEMO_DOCS);
  const [tab, setTab]             = useState('payments');
  const [refreshing, setRefresh]  = useState(false);
  const [isDemo, setIsDemo]       = useState(true);

  const loadData = async () => {
    try {
      const [wRes, dRes] = await Promise.all([getWallet(), getDocuments()]);
      setWallet(wRes.data);
      setPayments(wRes.data.payments || []);
      setDocs(dRes.data.items || []);
      setIsDemo(false);
    } catch {}
  };

  useEffect(() => { loadData(); }, []);

  const onRefresh = async () => { setRefresh(true); await loadData(); setRefresh(false); };

  const fmt = (n) => n?.toLocaleString('ru-RU') + ' ₽';

  const incomePercent = Math.round((wallet.income_this_year / wallet.income_limit) * 100);
  const incomeColor = incomePercent >= 90 ? '#e53935' : incomePercent >= 75 ? WARN : GREEN;

  // Панель выплат
  const PaymentsTab = () => (
    <>
      {payments.map(p => {
        const sc = STATUS_COLORS[p.status] || STATUS_COLORS.pending;
        return (
          <View key={p.id} style={s.payCard}>
            <View style={s.payTop}>
              <View style={s.payLeft}>
                <Text style={s.payTitle}>{p.task_title}</Text>
                <Text style={s.payStore}>{p.store}</Text>
                {p.doc_number && <Text style={s.payDoc}>📄 {p.doc_number}</Text>}
              </View>
              <View style={s.payRight}>
                <Text style={s.payAmount}>+{fmt(p.amount)}</Text>
                <Text style={s.payDate}>{p.date}</Text>
              </View>
            </View>
            <View style={[s.statusChip, { backgroundColor: sc.bg }]}>
              <Text style={[s.statusChipText, { color: sc.text }]}>{sc.label}</Text>
            </View>
          </View>
        );
      })}
    </>
  );

  // Панель документов
  const DocsTab = () => (
    <>
      {docs.map(d => {
        const sc  = STATUS_COLORS[d.status] || STATUS_COLORS.signed;
        const isAct = d.type === 'act';
        return (
          <View key={d.id} style={s.docCard}>
            <View style={s.docTop}>
              <Text style={s.docIcon}>{isAct ? '📋' : '📑'}</Text>
              <View style={s.docInfo}>
                <Text style={s.docTitle}>{d.title}</Text>
                <Text style={s.docNumber}>{d.number}</Text>
                <Text style={s.docDate}>{d.date}</Text>
              </View>
              <View style={[s.statusChip, { backgroundColor: sc.bg }]}>
                <Text style={[s.statusChipText, { color: sc.text }]}>{sc.label}</Text>
              </View>
            </View>
            {/* Кнопка "Подписать" для документов, ожидающих подписи */}
            {d.status === 'pending_sign' && (
              <TouchableOpacity style={s.signBtn}>
                <Text style={s.signBtnText}>✍️ Подписать через SMS</Text>
              </TouchableOpacity>
            )}
          </View>
        );
      })}
    </>
  );

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      {/* Шапка */}
      <View style={s.header}>
        <Text style={s.headerTitle}>Кошелёк</Text>
        {isDemo && <Text style={s.demoTag}>🛠 Демо</Text>}
      </View>

      <ScrollView
        style={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={KARI} />}
      >
        {/* Баланс */}
        <View style={s.balanceCard}>
          <Text style={s.balanceLabel}>Доступно к выводу</Text>
          <Text style={s.balanceMain}>{fmt(wallet.balance)}</Text>
          {wallet.pending > 0 && (
            <View style={s.pendingRow}>
              <Text style={s.pendingText}>⏳ Ожидает подтверждения: {fmt(wallet.pending)}</Text>
            </View>
          )}
        </View>

        {/* Сводка */}
        <View style={s.statsRow}>
          <View style={s.statCard}>
            <Text style={s.statValue}>{wallet.total_tasks}</Text>
            <Text style={s.statLabel}>Заданий{'\n'}выполнено</Text>
          </View>
          <View style={s.statCard}>
            <Text style={s.statValue}>{fmt(wallet.total_earned)}</Text>
            <Text style={s.statLabel}>Заработано{'\n'}всего</Text>
          </View>
        </View>

        {/* Лимит дохода */}
        <View style={s.limitCard}>
          <View style={s.limitHeader}>
            <Text style={s.limitTitle}>Годовой лимит дохода самозанятого</Text>
            <Text style={[s.limitPercent, { color: incomeColor }]}>{incomePercent}%</Text>
          </View>
          <View style={s.limitBar}>
            <View style={[s.limitFill, { width: `${Math.min(100, incomePercent)}%`, backgroundColor: incomeColor }]} />
          </View>
          <Text style={s.limitText}>
            {fmt(wallet.income_this_year)} из {fmt(wallet.income_limit)}{' '}
            {incomePercent >= 90 && '⚠️ Приближается лимит!'}
            {incomePercent >= 75 && incomePercent < 90 && '— будьте внимательны'}
          </Text>
        </View>

        {/* Блок: ИНН KARI для формирования чека (требование 422-ФЗ ст.14) */}
        <View style={s.innCard}>
          <View style={s.innRow}>
            <Text style={s.innIcon}>🧾</Text>
            <View style={s.innInfo}>
              <Text style={s.innTitle}>ИНН заказчика для чека</Text>
              <Text style={s.innValue}>7707023795</Text>
              <Text style={s.innSub}>ООО «КАРИ» — укажите при выписке чека{'\n'}в приложении «Мой налог»</Text>
            </View>
          </View>
          <Text style={s.innLaw}>По 422-ФЗ ст.14 чек нужно выдать не позднее 9-го числа следующего месяца</Text>
        </View>

        {/* Вкладки */}
        <View style={s.tabRow}>
          {TABS.map(t => (
            <TouchableOpacity
              key={t.key}
              style={[s.tabBtn, tab === t.key && s.tabBtnActive]}
              onPress={() => setTab(t.key)}
            >
              <Text style={[s.tabText, tab === t.key && s.tabTextActive]}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={s.tabContent}>
          {tab === 'payments' ? <PaymentsTab /> : <DocsTab />}
        </View>

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:   { flex: 1, backgroundColor: '#f0f2f5' },
  header: {
    backgroundColor: KARI, paddingHorizontal: 20, paddingVertical: 16,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '800', color: '#fff' },
  demoTag:     { fontSize: 12, color: 'rgba(255,255,255,0.7)', fontWeight: '600' },
  scroll:      { flex: 1 },

  balanceCard: {
    backgroundColor: DARK, margin: 16, borderRadius: 20, padding: 24, alignItems: 'center', gap: 8,
  },
  balanceLabel:  { fontSize: 13, color: 'rgba(255,255,255,0.6)' },
  balanceMain:   { fontSize: 40, fontWeight: '900', color: '#fff' },
  pendingRow:    { backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 5 },
  pendingText:   { fontSize: 13, color: 'rgba(255,255,255,0.8)' },

  statsRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 10, marginBottom: 10 },
  statCard: {
    flex: 1, backgroundColor: '#fff', borderRadius: 14, padding: 16, alignItems: 'center',
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 6, elevation: 2,
  },
  statValue: { fontSize: 20, fontWeight: '800', color: KARI },
  statLabel: { fontSize: 12, color: '#888', textAlign: 'center', marginTop: 4, lineHeight: 16 },

  limitCard: {
    backgroundColor: '#fff', marginHorizontal: 16, borderRadius: 14,
    padding: 16, marginBottom: 10,
  },
  limitHeader:  { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  limitTitle:   { fontSize: 13, fontWeight: '600', color: DARK },
  limitPercent: { fontSize: 16, fontWeight: '800' },
  limitBar:     { height: 8, backgroundColor: '#f0f0f0', borderRadius: 4, overflow: 'hidden', marginBottom: 6 },
  limitFill:    { height: '100%', borderRadius: 4 },
  limitText:    { fontSize: 12, color: '#888' },

  tabRow: {
    flexDirection: 'row', marginHorizontal: 16, marginBottom: 10,
    backgroundColor: '#fff', borderRadius: 12, padding: 4, gap: 4,
  },
  tabBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center',
  },
  tabBtnActive: { backgroundColor: KARI },
  tabText:      { fontSize: 13, fontWeight: '600', color: '#666' },
  tabTextActive:{ color: '#fff' },

  tabContent: { paddingHorizontal: 16, gap: 10 },

  payCard: {
    backgroundColor: '#fff', borderRadius: 14, padding: 14, gap: 8,
  },
  payTop:    { flexDirection: 'row', justifyContent: 'space-between' },
  payLeft:   { flex: 1, marginRight: 12 },
  payTitle:  { fontSize: 14, fontWeight: '700', color: DARK },
  payStore:  { fontSize: 12, color: '#666', marginTop: 2 },
  payDoc:    { fontSize: 11, color: '#888', marginTop: 2 },
  payRight:  { alignItems: 'flex-end' },
  payAmount: { fontSize: 18, fontWeight: '800', color: GREEN },
  payDate:   { fontSize: 12, color: '#888', marginTop: 2 },

  statusChip: { alignSelf: 'flex-start', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  statusChipText: { fontSize: 12, fontWeight: '600' },

  docCard: {
    backgroundColor: '#fff', borderRadius: 14, padding: 14, gap: 10,
  },
  docTop:   { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  docIcon:  { fontSize: 28 },
  docInfo:  { flex: 1 },
  docTitle: { fontSize: 15, fontWeight: '700', color: DARK },
  docNumber:{ fontSize: 12, color: '#888', marginTop: 2 },
  docDate:  { fontSize: 12, color: '#888', marginTop: 1 },

  signBtn: {
    backgroundColor: KARI, borderRadius: 10, paddingVertical: 12, alignItems: 'center',
  },
  signBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },

  // Блок ИНН KARI
  innCard: {
    backgroundColor: '#fff', marginHorizontal: 16, borderRadius: 14,
    padding: 14, marginBottom: 10,
    borderLeftWidth: 4, borderLeftColor: KARI,
  },
  innRow:   { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 8 },
  innIcon:  { fontSize: 26, marginTop: 2 },
  innInfo:  { flex: 1 },
  innTitle: { fontSize: 11, fontWeight: '800', color: '#888', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 },
  innValue: { fontSize: 22, fontWeight: '900', color: DARK, letterSpacing: 1, marginBottom: 2 },
  innSub:   { fontSize: 12, color: '#666', lineHeight: 17 },
  innLaw:   { fontSize: 11, color: '#aaa', fontStyle: 'italic', lineHeight: 16 },
});
