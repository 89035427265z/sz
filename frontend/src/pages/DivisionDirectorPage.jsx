// =============================================================================
// KARI.Самозанятые — Кабинет директора подразделения
// =============================================================================
// Директор подразделения видит:
//   - Магазины своего подразделения с бюджетами
//   - Сводную статистику по заданиям
//   - Исполнителей с риск-индикаторами
//   - Может провалиться в любой магазин

import { useState } from 'react'

// ─── Демо-данные ──────────────────────────────────────────────────────────

const DEMO_DIVISION = {
  name:         'Иркутск Запад',
  region_name:  'Иркутский регион',
  budget_total: 600_000,
  budget_used:  522_000,
}

const DEMO_STORES = [
  {
    id:'s1', name:'ТЦ «Мегас»',
    address:'г. Иркутск, Сергеева, 3',
    budget_total:300_000, budget_used:285_000,
    executors:9, tasks_active:4, tasks_submitted:2,
    risk:'budget',
    executors_list: [
      { name:'Иванов И.И.', inn:'381234560001', income_pct:91, fns:'active' },
      { name:'Смирнова А.А.', inn:'381234560002', income_pct:45, fns:'active' },
      { name:'Петров В.С.', inn:'381234560003', income_pct:62, fns:'active' },
    ],
  },
  {
    id:'s2', name:'ТЦ «Сильвер Молл»',
    address:'г. Иркутск, Трактовая, 12',
    budget_total:200_000, budget_used:145_000,
    executors:8, tasks_active:3, tasks_submitted:0,
    risk: null,
    executors_list: [
      { name:'Козлов М.Р.', inn:'381234560004', income_pct:33, fns:'active' },
      { name:'Новикова Е.В.', inn:'381234560005', income_pct:15, fns:'active' },
    ],
  },
  {
    id:'s3', name:'ТЦ «Аквамолл»',
    address:'г. Иркутск, ул. Баумана, 220',
    budget_total:100_000, budget_used:92_000,
    executors:4, tasks_active:1, tasks_submitted:1,
    risk:'budget',
    executors_list: [
      { name:'Фёдоров Д.П.', inn:'381234560006', income_pct:78, fns:'active' },
      { name:'Кузнецова О.Л.', inn:'381234560007', income_pct:22, fns:'inactive' },
    ],
  },
]

// ─── Компоненты ──────────────────────────────────────────────────────────────

function ProgressBar({ value, warn }) {
  const pct = Math.min(100, value)
  const color = warn || pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981'
  return (
    <div style={{ background:'#e5e7eb', borderRadius:4, height:8, overflow:'hidden' }}>
      <div style={{ width:`${pct}%`, height:'100%', background:color, borderRadius:4, transition:'width .4s' }} />
    </div>
  )
}

function RiskBadge({ risk }) {
  if (!risk) return null
  return (
    <span style={{ background:'#fef2f2', color:'#dc2626', fontSize:10, fontWeight:700,
      padding:'2px 7px', borderRadius:8, border:'1px solid #fecaca' }}>
      ⚠️ Риск бюджета
    </span>
  )
}

// ─── Детальная карточка магазина ──────────────────────────────────────────

function StoreDetail({ store, onClose }) {
  const budgetPct = Math.round(store.budget_used / store.budget_total * 100)
  const freeAmount = store.budget_total - store.budget_used

  return (
    <div style={sd.overlay} onClick={onClose}>
      <div style={sd.panel} onClick={e => e.stopPropagation()}>
        <div style={sd.header}>
          <div>
            <h3 style={sd.title}>{store.name}</h3>
            <p style={sd.addr}>{store.address}</p>
          </div>
          <button onClick={onClose} style={sd.closeBtn}>✕</button>
        </div>

        {/* Бюджет */}
        <div style={sd.section}>
          <div style={sd.sectionTitle}>💼 Бюджет магазина</div>
          <div style={sd.budgetRow}>
            <div style={sd.budgetItem}>
              <div style={sd.budgetLabel}>Использовано</div>
              <div style={{ ...sd.budgetVal, color:'#A01F72' }}>
                {store.budget_used.toLocaleString('ru-RU')} ₽
              </div>
            </div>
            <div style={sd.budgetItem}>
              <div style={sd.budgetLabel}>Лимит</div>
              <div style={sd.budgetVal}>{store.budget_total.toLocaleString('ru-RU')} ₽</div>
            </div>
            <div style={sd.budgetItem}>
              <div style={sd.budgetLabel}>Остаток</div>
              <div style={{ ...sd.budgetVal, color: freeAmount < 20000 ? '#dc2626' : '#16a34a' }}>
                {freeAmount.toLocaleString('ru-RU')} ₽
              </div>
            </div>
          </div>
          <ProgressBar value={budgetPct} warn={budgetPct >= 90} />
          <div style={sd.budgetPct}>{budgetPct}% бюджета использовано</div>
        </div>

        {/* Задания */}
        <div style={sd.section}>
          <div style={sd.sectionTitle}>📋 Задания</div>
          <div style={sd.statsRow}>
            <div style={sd.stat}>
              <span style={sd.statNum}>{store.tasks_active}</span>
              <span style={sd.statLabel}>активных</span>
            </div>
            <div style={{ ...sd.stat, color: store.tasks_submitted > 0 ? '#d97706' : undefined }}>
              <span style={sd.statNum}>{store.tasks_submitted}</span>
              <span style={sd.statLabel}>на проверке</span>
            </div>
            <div style={sd.stat}>
              <span style={sd.statNum}>{store.executors}</span>
              <span style={sd.statLabel}>исполнителей</span>
            </div>
          </div>
        </div>

        {/* Исполнители */}
        <div style={sd.section}>
          <div style={sd.sectionTitle}>👥 Исполнители</div>
          <div style={sd.executorList}>
            {store.executors_list.map((ex, i) => (
              <div key={i} style={sd.executorRow}>
                <div>
                  <div style={sd.exName}>{ex.name}</div>
                  <div style={sd.exInn}>ИНН {ex.inn}</div>
                </div>
                <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4, minWidth:120 }}>
                  <div style={{ display:'flex', gap:6, alignItems:'center' }}>
                    {ex.fns !== 'active' && (
                      <span style={{ background:'#fef2f2', color:'#dc2626', fontSize:10,
                        fontWeight:700, padding:'1px 6px', borderRadius:6 }}>ФНС⚠️</span>
                    )}
                    <span style={{
                      fontSize:11, fontWeight:700,
                      color: ex.income_pct >= 80 ? '#dc2626' : ex.income_pct >= 60 ? '#d97706' : '#16a34a'
                    }}>{ex.income_pct}% дохода</span>
                  </div>
                  <div style={{ width:100 }}>
                    <ProgressBar value={ex.income_pct} warn={ex.income_pct >= 80} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={sd.footer}>
          <button onClick={onClose} style={sd.btnClose}>Закрыть</button>
        </div>
      </div>
    </div>
  )
}

// ─── Главный компонент ────────────────────────────────────────────────────

export default function DivisionDirectorPage() {
  const [openStore, setOpenStore] = useState(null)

  const divBudgetPct  = Math.round(DEMO_DIVISION.budget_used / DEMO_DIVISION.budget_total * 100)
  const totalExecutors = DEMO_STORES.reduce((a, s) => a + s.executors, 0)
  const totalTasks     = DEMO_STORES.reduce((a, s) => a + s.tasks_active, 0)
  const pendingAll     = DEMO_STORES.reduce((a, s) => a + s.tasks_submitted, 0)
  const riskyStores    = DEMO_STORES.filter(s => s.risk).length

  const storeDetail = openStore ? DEMO_STORES.find(s => s.id === openStore) : null

  return (
    <div style={{ fontFamily:'Nunito,sans-serif', maxWidth:860 }}>

      {/* ── Шапка ── */}
      <div style={p.header}>
        <div>
          <h1 style={p.pageTitle}>Подразделение: {DEMO_DIVISION.name}</h1>
          <p style={p.pageSubtitle}>{DEMO_DIVISION.region_name}</p>
        </div>
        <span style={p.demoBadge}>🛠 Демо</span>
      </div>

      {/* ── Метрики подразделения ── */}
      <div style={p.metrics}>
        <div style={{ ...p.metricCard, gridColumn:'span 2' }}>
          <div style={p.metricLabel}>Бюджет подразделения</div>
          <div style={p.metricRow}>
            <div style={{ ...p.metricBig, color:'#A01F72' }}>
              {DEMO_DIVISION.budget_used.toLocaleString('ru-RU')} ₽
            </div>
            <div style={p.metricOfTotal}>
              из {DEMO_DIVISION.budget_total.toLocaleString('ru-RU')} ₽
            </div>
          </div>
          <div style={{ marginTop:10 }}>
            <ProgressBar value={divBudgetPct} warn={divBudgetPct >= 85} />
          </div>
          <div style={p.metricSub}>{divBudgetPct}% — {(DEMO_DIVISION.budget_total - DEMO_DIVISION.budget_used).toLocaleString('ru-RU')} ₽ остаток</div>
        </div>

        <div style={p.metricCard}>
          <div style={p.metricLabel}>Магазинов</div>
          <div style={p.metricBig}>{DEMO_STORES.length}</div>
          <div style={p.metricSub}>{riskyStores > 0 ? `⚠️ ${riskyStores} с риском бюджета` : 'Всё в норме'}</div>
        </div>
        <div style={p.metricCard}>
          <div style={p.metricLabel}>Исполнителей</div>
          <div style={p.metricBig}>{totalExecutors}</div>
          <div style={p.metricSub}>{totalTasks} активных заданий</div>
        </div>
        {pendingAll > 0 && (
          <div style={{ ...p.metricCard, background:'#fffbeb', borderColor:'#fbbf24' }}>
            <div style={p.metricLabel}>На проверке</div>
            <div style={{ ...p.metricBig, color:'#d97706' }}>{pendingAll}</div>
            <div style={p.metricSub}>⚠️ Ждут директоров магазинов</div>
          </div>
        )}
      </div>

      {/* ── Магазины ── */}
      <h2 style={p.sectionTitle}>🏪 Магазины подразделения</h2>
      <div style={p.storeGrid}>
        {DEMO_STORES.map(store => {
          const pct = Math.round(store.budget_used / store.budget_total * 100)
          const free = store.budget_total - store.budget_used
          return (
            <div key={store.id} style={{ ...p.storeCard, borderColor: store.risk ? '#fca5a5' : '#e5e7eb' }}>
              <div style={p.storeCardHead}>
                <div>
                  <div style={p.storeName}>{store.name}</div>
                  <div style={p.storeAddr}>{store.address}</div>
                </div>
                {store.risk && <RiskBadge risk={store.risk} />}
              </div>

              {/* Бюджет */}
              <div style={p.storeSection}>
                <div style={p.storeBudgetRow}>
                  <span style={p.storeBudgetLabel}>Бюджет</span>
                  <span style={{ fontWeight:700, color: pct >= 90 ? '#dc2626' : '#111827' }}>
                    {pct}%
                  </span>
                </div>
                <ProgressBar value={pct} warn={pct >= 90} />
                <div style={p.storeBudgetSub}>
                  {store.budget_used.toLocaleString('ru-RU')} ₽ &nbsp;/&nbsp; {store.budget_total.toLocaleString('ru-RU')} ₽
                  &nbsp;·&nbsp; остаток: <b>{free.toLocaleString('ru-RU')} ₽</b>
                </div>
              </div>

              {/* Статистика */}
              <div style={p.storeStats}>
                <div style={p.storeStat}>
                  <div style={p.storeStatNum}>{store.tasks_active}</div>
                  <div style={p.storeStatLbl}>заданий</div>
                </div>
                <div style={{ ...p.storeStat, color: store.tasks_submitted > 0 ? '#d97706' : undefined }}>
                  <div style={{ ...p.storeStatNum, color: store.tasks_submitted > 0 ? '#d97706' : undefined }}>
                    {store.tasks_submitted}
                  </div>
                  <div style={p.storeStatLbl}>на проверке</div>
                </div>
                <div style={p.storeStat}>
                  <div style={p.storeStatNum}>{store.executors}</div>
                  <div style={p.storeStatLbl}>исполнителей</div>
                </div>
              </div>

              <button onClick={() => setOpenStore(store.id)} style={p.btnDetail}>
                Подробнее →
              </button>
            </div>
          )
        })}
      </div>

      {/* ── Детальная карточка ── */}
      {storeDetail && (
        <StoreDetail store={storeDetail} onClose={() => setOpenStore(null)} />
      )}
    </div>
  )
}

// ─── Стили ────────────────────────────────────────────────────────────────
const p = {
  header:       { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:24 },
  pageTitle:    { fontSize:22, fontWeight:800, color:'#111827', margin:0 },
  pageSubtitle: { fontSize:13, color:'#6b7280', margin:'4px 0 0' },
  demoBadge:    { background:'#fef3c7', color:'#92400e', fontSize:11, fontWeight:700, padding:'4px 10px', borderRadius:6, flexShrink:0 },
  metrics:      { display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:28 },
  metricCard:   { background:'#fff', border:'1.5px solid #e5e7eb', borderRadius:12, padding:'16px 18px' },
  metricLabel:  { fontSize:12, color:'#6b7280', fontWeight:600, marginBottom:6 },
  metricRow:    { display:'flex', alignItems:'baseline', gap:8 },
  metricBig:    { fontSize:26, fontWeight:800, color:'#111827' },
  metricOfTotal:{ fontSize:13, color:'#9ca3af', fontWeight:600 },
  metricSub:    { fontSize:11, color:'#9ca3af', marginTop:8 },
  sectionTitle: { fontSize:15, fontWeight:800, color:'#242D4A', marginBottom:14 },
  storeGrid:    { display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16 },
  storeCard:    { background:'#fff', border:'1.5px solid #e5e7eb', borderRadius:12, padding:'18px', display:'flex', flexDirection:'column', gap:12 },
  storeCardHead:{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:8 },
  storeName:    { fontSize:14, fontWeight:800, color:'#111827' },
  storeAddr:    { fontSize:11, color:'#9ca3af', marginTop:3 },
  storeSection: { display:'flex', flexDirection:'column', gap:6 },
  storeBudgetRow:{ display:'flex', justifyContent:'space-between', fontSize:12, fontWeight:600, color:'#374151' },
  storeBudgetLabel:{ color:'#6b7280' },
  storeBudgetSub:{ fontSize:11, color:'#9ca3af' },
  storeStats:   { display:'flex', justifyContent:'space-around', background:'#f9fafb', borderRadius:8, padding:'10px 8px' },
  storeStat:    { textAlign:'center' },
  storeStatNum: { fontSize:18, fontWeight:800, color:'#111827' },
  storeStatLbl: { fontSize:10, color:'#9ca3af', fontWeight:600 },
  btnDetail:    { background:'#fdf4fb', color:'#A01F72', border:'1px solid #f9a8d4', borderRadius:8, padding:'8px 0', fontSize:13, fontWeight:700, cursor:'pointer', fontFamily:'inherit', width:'100%', textAlign:'center' },
}

const sd = {
  overlay:   { position:'fixed', inset:0, background:'rgba(0,0,0,.45)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'flex-end' },
  panel:     { background:'#fff', width:'420px', height:'100%', overflowY:'auto', boxShadow:'-8px 0 40px rgba(0,0,0,.15)', display:'flex', flexDirection:'column' },
  header:    { display:'flex', justifyContent:'space-between', alignItems:'flex-start', padding:'24px 24px 0', gap:12 },
  title:     { fontSize:16, fontWeight:800, color:'#111827', margin:0 },
  addr:      { fontSize:12, color:'#9ca3af', margin:'4px 0 0' },
  closeBtn:  { background:'none', border:'none', fontSize:20, cursor:'pointer', color:'#9ca3af', lineHeight:1, flexShrink:0 },
  section:   { padding:'20px 24px', borderBottom:'1px solid #f3f4f6' },
  sectionTitle:{ fontSize:13, fontWeight:800, color:'#374151', marginBottom:12 },
  budgetRow: { display:'flex', gap:16, marginBottom:10 },
  budgetItem:{ flex:1 },
  budgetLabel:{ fontSize:11, color:'#9ca3af', fontWeight:600, marginBottom:2 },
  budgetVal: { fontSize:16, fontWeight:800, color:'#111827' },
  budgetPct: { fontSize:11, color:'#9ca3af', marginTop:6 },
  statsRow:  { display:'flex', gap:20 },
  stat:      { display:'flex', flexDirection:'column', alignItems:'center' },
  statNum:   { fontSize:22, fontWeight:800, color:'#111827' },
  statLabel: { fontSize:11, color:'#9ca3af', fontWeight:600 },
  executorList:{ display:'flex', flexDirection:'column', gap:10 },
  executorRow:{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'8px 0', borderBottom:'1px solid #f3f4f6' },
  exName:    { fontSize:13, fontWeight:700, color:'#111827' },
  exInn:     { fontSize:11, color:'#9ca3af' },
  footer:    { padding:'20px 24px', marginTop:'auto' },
  btnClose:  { width:'100%', background:'#f3f4f6', color:'#374151', border:'none', borderRadius:8, padding:'10px', fontSize:13, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
}
