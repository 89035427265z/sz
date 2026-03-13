// =============================================================================
// KARI.Самозанятые — Кабинет HRD / Бухгалтерии
// =============================================================================
// HRD и бухгалтер видят:
//   - Всех исполнителей с ФНС-статусом и риск-контролем доходов
//   - Все договоры и акты (ЭДО)
//   - Выплаты и реестры
//   - ФНС-чеки
//   - Аналитику по регионам

import { useState } from 'react'

// ─── Демо-данные ──────────────────────────────────────────────────────────

const DEMO_EXECUTORS = [
  { id:'e1', name:'Иванов Иван Иванович',     inn:'381234560001', phone:'+7 914 123-45-01', store:'ТЦ «Мегас»',        income_kari:2_180_000, income_total:2_390_000, fns:'active',   status:'active' },
  { id:'e2', name:'Сидорова Анна Викторовна', inn:'381234560002', phone:'+7 914 123-45-02', store:'ТЦ «Мегас»',        income_kari:1_080_000, income_total:2_400_000, fns:'active',   status:'active' },
  { id:'e3', name:'Петров Владимир Сергеевич',inn:'381234560003', phone:'+7 914 123-45-03', store:'ТЦ «Карамель»',     income_kari:  930_000, income_total:1_500_000, fns:'active',   status:'active' },
  { id:'e4', name:'Козлов Михаил Романович',  inn:'381234560004', phone:'+7 914 123-45-04', store:'ТЦ «Сильвер Молл»',income_kari:  496_000, income_total:1_500_000, fns:'active',   status:'active' },
  { id:'e5', name:'Кузнецова Ольга Леонидовна',inn:'381234560007',phone:'+7 914 123-45-07', store:'ТЦ «Аквамолл»',    income_kari:  210_000, income_total:  210_000, fns:'inactive', status:'blocked' },
  { id:'e6', name:'Фёдоров Дмитрий Павлович', inn:'381234560006', phone:'+7 914 123-45-06', store:'ТЦ «Аквамолл»',    income_kari:1_870_000, income_total:2_400_000, fns:'active',   status:'active' },
  { id:'e7', name:'Новикова Елена Вадимовна', inn:'381234560005', phone:'+7 914 123-45-05', store:'ТЦ «Сильвер Молл»',income_kari:  360_000, income_total:2_400_000, fns:'active',   status:'active' },
]

const DEMO_DOCUMENTS = [
  { id:'d1', number:'KARI-2026-ДГ-A1B2C3', type:'contract', status:'signed',       executor:'Иванов И.И.',      task:'Уборка зала', amount:'1 500,00', date:'01.04.2026' },
  { id:'d2', number:'KARI-2026-АКТ-D4E5F6',type:'act',      status:'signed',       executor:'Иванов И.И.',      task:'Уборка зала', amount:'1 500,00', date:'01.04.2026' },
  { id:'d3', number:'KARI-2026-ДГ-G7H8I9', type:'contract', status:'pending_sign', executor:'Сидорова А.В.',    task:'Выкладка коллекции', amount:'2 200,00', date:'01.04.2026' },
  { id:'d4', number:'KARI-2026-ДГ-J1K2L3', type:'contract', status:'signed',       executor:'Петров В.С.',      task:'Инвентаризация', amount:'3 000,00', date:'31.03.2026' },
  { id:'d5', number:'KARI-2026-АКТ-M4N5O6',type:'act',      status:'draft',        executor:'Козлов М.Р.',      task:'Разгрузка товара', amount:'1 800,00', date:'31.03.2026' },
]

const DEMO_PAYMENTS = [
  { id:'p1', executor:'Иванов И.И.',      amount:1_500, status:'completed', date:'02.04.2026', task:'Уборка зала', check_num:'ЧЕК-001' },
  { id:'p2', executor:'Петров В.С.',      amount:3_000, status:'completed', date:'01.04.2026', task:'Инвентаризация', check_num:'ЧЕК-002' },
  { id:'p3', executor:'Сидорова А.В.',    amount:2_200, status:'pending',   date:'—', task:'Выкладка коллекции', check_num:'—' },
  { id:'p4', executor:'Фёдоров Д.П.',     amount:1_200, status:'failed',    date:'—', task:'Промо-акция', check_num:'—' },
  { id:'p5', executor:'Козлов М.Р.',      amount:1_800, status:'pending',   date:'—', task:'Разгрузка товара', check_num:'—' },
]

const DEMO_ANALYTICS = {
  total_executors: 63, active_executors: 58, blocked: 5,
  fns_active: 56, fns_inactive: 7,
  risk_high: 4, risk_medium: 11,
  income_limit_near: 3,
  payments_month: 187_400, payments_count: 42,
  tasks_completed: 38, tasks_active: 19,
  docs_signed: 76, docs_pending: 3,
}

// ─── Утилиты ─────────────────────────────────────────────────────────────

const INCOME_LIMIT = 2_400_000
const fmtRub = n => n.toLocaleString('ru-RU') + ' ₽'

function incomeRiskPct(kari, total) {
  if (!total) return 0
  return Math.round(kari / total * 100)
}

function incomeLimitPct(kari) {
  return Math.round(kari / INCOME_LIMIT * 100)
}

// ─── Общие компоненты ────────────────────────────────────────────────────

function ProgressBar({ value, warn, height = 7 }) {
  const pct = Math.min(100, value)
  const color = warn || pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981'
  return (
    <div style={{ background:'#e5e7eb', borderRadius:4, height, overflow:'hidden' }}>
      <div style={{ width:`${pct}%`, height:'100%', background:color, borderRadius:4, transition:'width .4s' }} />
    </div>
  )
}

const FNS_META  = { active:['✅','#16a34a','#f0fdf4'], inactive:['⛔','#dc2626','#fef2f2'], blocked:['🔒','#9ca3af','#f3f4f6'] }
const PAY_META  = { completed:['Выплачено','#16a34a','#f0fdf4'], pending:['Ожидает','#d97706','#fffbeb'], failed:['Ошибка','#dc2626','#fef2f2'] }
const DOC_META  = { signed:['Подписан','#16a34a','#f0fdf4'], pending_sign:['Ждёт подписи','#d97706','#fffbeb'], draft:['Черновик','#6b7280','#f3f4f6'], cancelled:['Отменён','#dc2626','#fef2f2'] }
const DOC_TYPES = { contract:'Договор ГПХ', act:'Акт' }

function StatusChip({ label, color, bg }) {
  return (
    <span style={{ background:bg, color, fontSize:11, fontWeight:700,
      padding:'2px 8px', borderRadius:10, whiteSpace:'nowrap' }}>
      {label}
    </span>
  )
}

// ─── Вкладка: Исполнители ─────────────────────────────────────────────────

function ExecutorsTab() {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')

  const filtered = DEMO_EXECUTORS.filter(e => {
    const q = search.toLowerCase()
    const matchSearch = !q || e.name.toLowerCase().includes(q) || e.inn.includes(q)
    const matchFilter =
      filter === 'all'     ? true :
      filter === 'risk'    ? incomeRiskPct(e.income_kari, e.income_total) >= 70 :
      filter === 'limit'   ? incomeLimitPct(e.income_kari) >= 80 :
      filter === 'problem' ? e.fns !== 'active' || e.status !== 'active' : true
    return matchSearch && matchFilter
  })

  return (
    <div>
      {/* Фильтры */}
      <div style={h.filterRow}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="🔍 Поиск по имени или ИНН..."
          style={h.searchInput}
        />
        <div style={h.filterBtns}>
          {[
            ['all',     'Все'],
            ['risk',    '⚠️ Риск 80%'],
            ['limit',   '📊 Лимит дохода'],
            ['problem', '🔴 Проблемные'],
          ].map(([v, l]) => (
            <button
              key={v}
              onClick={() => setFilter(v)}
              style={{ ...h.filterBtn, ...(filter === v ? h.filterBtnActive : {}) }}
            >{l}</button>
          ))}
        </div>
      </div>

      {/* Таблица */}
      <div style={h.tableWrap}>
        <table style={h.table}>
          <thead>
            <tr style={h.thead}>
              <th style={h.th}>Исполнитель</th>
              <th style={h.th}>Магазин</th>
              <th style={h.th}>ФНС</th>
              <th style={{ ...h.th, width:180 }}>Доход от KARI</th>
              <th style={{ ...h.th, width:180 }}>Риск 80%</th>
              <th style={h.th}>Статус</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(e => {
              const limitPct = incomeLimitPct(e.income_kari)
              const riskPct  = incomeRiskPct(e.income_kari, e.income_total)
              const [fIcon, fColor, fBg] = FNS_META[e.fns] || FNS_META.inactive
              return (
                <tr key={e.id} style={h.tr}>
                  <td style={h.td}>
                    <div style={h.exName}>{e.name}</div>
                    <div style={h.exMeta}>{e.inn} · {e.phone}</div>
                  </td>
                  <td style={h.td}><span style={h.storeName}>{e.store}</span></td>
                  <td style={h.td}>
                    <span style={{ background:fBg, color:fColor, fontSize:11, fontWeight:700,
                      padding:'2px 8px', borderRadius:10 }}>{fIcon} {e.fns === 'active' ? 'Активен' : 'Не самозанятый'}</span>
                  </td>
                  <td style={h.td}>
                    <div style={h.incomeRow}>
                      <span style={{ fontSize:12, fontWeight:700,
                        color: limitPct >= 90 ? '#dc2626' : limitPct >= 70 ? '#d97706' : '#111827' }}>
                        {fmtRub(e.income_kari)}
                      </span>
                      <span style={{ fontSize:10, color:'#9ca3af' }}>{limitPct}%</span>
                    </div>
                    <ProgressBar value={limitPct} warn={limitPct >= 80} height={5} />
                  </td>
                  <td style={h.td}>
                    <div style={h.incomeRow}>
                      <span style={{ fontSize:12, fontWeight:700,
                        color: riskPct >= 80 ? '#dc2626' : riskPct >= 60 ? '#d97706' : '#6b7280' }}>
                        {riskPct}%
                      </span>
                      {riskPct >= 80 && <span style={h.riskBadge}>⚠️ Риск</span>}
                    </div>
                    <ProgressBar value={riskPct} warn={riskPct >= 80} height={5} />
                  </td>
                  <td style={h.td}>
                    <StatusChip
                      label={e.status === 'active' ? 'Активен' : 'Заблокирован'}
                      color={e.status === 'active' ? '#16a34a' : '#dc2626'}
                      bg={e.status === 'active' ? '#f0fdf4' : '#fef2f2'}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div style={h.empty}>Нет исполнителей по заданным фильтрам</div>
        )}
      </div>
    </div>
  )
}

// ─── Вкладка: Договоры и акты ────────────────────────────────────────────

function DocumentsTab() {
  const [typeFilter, setTypeFilter] = useState('all')
  const filtered = DEMO_DOCUMENTS.filter(d =>
    typeFilter === 'all' ? true : d.type === typeFilter
  )
  return (
    <div>
      <div style={h.filterRow}>
        <div style={h.filterBtns}>
          {[['all','Все документы'],['contract','Договоры ГПХ'],['act','Акты']].map(([v,l]) => (
            <button key={v} onClick={() => setTypeFilter(v)}
              style={{ ...h.filterBtn, ...(typeFilter === v ? h.filterBtnActive : {}) }}>{l}</button>
          ))}
        </div>
      </div>
      <div style={h.tableWrap}>
        <table style={h.table}>
          <thead>
            <tr style={h.thead}>
              <th style={h.th}>Номер</th>
              <th style={h.th}>Тип</th>
              <th style={h.th}>Исполнитель</th>
              <th style={h.th}>Задание</th>
              <th style={h.th}>Сумма</th>
              <th style={h.th}>Дата</th>
              <th style={h.th}>Статус</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(doc => {
              const [label, color, bg] = DOC_META[doc.status] || DOC_META.draft
              return (
                <tr key={doc.id} style={h.tr}>
                  <td style={h.td}><span style={h.monoText}>{doc.number}</span></td>
                  <td style={h.td}><span style={h.typeChip}>{DOC_TYPES[doc.type]}</span></td>
                  <td style={h.td}>{doc.executor}</td>
                  <td style={h.td}>{doc.task}</td>
                  <td style={h.td}><b>{doc.amount} ₽</b></td>
                  <td style={h.td}>{doc.date}</td>
                  <td style={h.td}><StatusChip label={label} color={color} bg={bg} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Вкладка: Выплаты ────────────────────────────────────────────────────

function PaymentsTab() {
  return (
    <div>
      <div style={{ display:'flex', gap:16, marginBottom:20 }}>
        {[
          ['Выплачено (месяц)', fmtRub(DEMO_ANALYTICS.payments_month), '#16a34a'],
          ['Транзакций', DEMO_ANALYTICS.payments_count, '#111827'],
          ['Ожидают оплаты', DEMO_PAYMENTS.filter(p=>p.status==='pending').length, '#d97706'],
          ['Ошибки', DEMO_PAYMENTS.filter(p=>p.status==='failed').length, '#dc2626'],
        ].map(([l, v, c]) => (
          <div key={l} style={{ ...h.miniCard, flex:1 }}>
            <div style={h.miniLabel}>{l}</div>
            <div style={{ ...h.miniVal, color:c }}>{v}</div>
          </div>
        ))}
      </div>
      <div style={h.tableWrap}>
        <table style={h.table}>
          <thead>
            <tr style={h.thead}>
              <th style={h.th}>Исполнитель</th>
              <th style={h.th}>Задание</th>
              <th style={h.th}>Сумма</th>
              <th style={h.th}>Дата выплаты</th>
              <th style={h.th}>Чек ФНС</th>
              <th style={h.th}>Статус</th>
            </tr>
          </thead>
          <tbody>
            {DEMO_PAYMENTS.map(pay => {
              const [label, color, bg] = PAY_META[pay.status] || PAY_META.pending
              return (
                <tr key={pay.id} style={h.tr}>
                  <td style={h.td}>{pay.executor}</td>
                  <td style={h.td}>{pay.task}</td>
                  <td style={h.td}><b style={{ color:'#A01F72' }}>{fmtRub(pay.amount)}</b></td>
                  <td style={h.td}>{pay.date}</td>
                  <td style={h.td}><span style={h.monoText}>{pay.check_num}</span></td>
                  <td style={h.td}><StatusChip label={label} color={color} bg={bg} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Вкладка: Аналитика ──────────────────────────────────────────────────

function AnalyticsTab() {
  const a = DEMO_ANALYTICS
  const cards = [
    { title:'👥 Исполнители', items:[
      [`Всего`, a.total_executors],
      [`Активных`, a.active_executors],
      [`Заблокировано`, a.blocked],
    ]},
    { title:'🏛️ ФНС / Налоги', items:[
      [`Статус ФНС ✅`, a.fns_active],
      [`Не самозанятые`, a.fns_inactive],
      [`Лимит дохода ≥80%`, a.income_limit_near],
    ]},
    { title:'⚠️ Риски', items:[
      [`Риск 80% (критично)`, a.risk_high],
      [`Риск 60–79%`, a.risk_medium],
      [`Закончился лимит`, 0],
    ]},
    { title:'💰 Финансы (апрель)', items:[
      [`Выплат итого`, fmtRub(a.payments_month)],
      [`Транзакций`, a.payments_count],
      [`Ср. выплата`, fmtRub(Math.round(a.payments_month / a.payments_count))],
    ]},
    { title:'📋 Задания', items:[
      [`Завершено`, a.tasks_completed],
      [`Активных`, a.tasks_active],
      [`Всего ЭДО`, a.docs_signed + a.docs_pending],
    ]},
    { title:'📄 Документы ЭДО', items:[
      [`Подписано`, a.docs_signed],
      [`Ожидают подписи`, a.docs_pending],
      [`Итого`, a.docs_signed + a.docs_pending],
    ]},
  ]

  return (
    <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16 }}>
      {cards.map(card => (
        <div key={card.title} style={h.analyticsCard}>
          <div style={h.analyticsTitle}>{card.title}</div>
          {card.items.map(([label, val]) => (
            <div key={label} style={h.analyticsRow}>
              <span style={h.analyticsLabel}>{label}</span>
              <span style={h.analyticsVal}>{val}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ─── Главный компонент ────────────────────────────────────────────────────

const TABS = [
  { id:'executors',  label:'👥 Исполнители' },
  { id:'documents',  label:'📄 Договоры' },
  { id:'payments',   label:'💰 Выплаты' },
  { id:'analytics',  label:'📈 Аналитика' },
]

export default function HrdPage() {
  const [activeTab, setActiveTab] = useState('executors')
  const a = DEMO_ANALYTICS

  return (
    <div style={{ fontFamily:'Nunito,sans-serif', maxWidth:1100 }}>

      {/* ── Шапка ── */}
      <div style={h.header}>
        <div>
          <h1 style={h.pageTitle}>Кабинет HRD / Бухгалтерии</h1>
          <p style={h.pageSubtitle}>Иркутский регион · Пилот Апрель 2026</p>
        </div>
        <span style={h.demoBadge}>🛠 Демо</span>
      </div>

      {/* ── Сигналы ── */}
      {(a.risk_high > 0 || a.fns_inactive > 0 || a.income_limit_near > 0) && (
        <div style={h.signalsRow}>
          {a.fns_inactive > 0 && (
            <div style={h.signal}>
              ⛔ <b>{a.fns_inactive} исполнителей</b> утратили статус самозанятого — нельзя выдавать задания
            </div>
          )}
          {a.risk_high > 0 && (
            <div style={h.signal}>
              ⚠️ <b>{a.risk_high} исполнителя</b> с риском 80% — переквалификация в сотрудника
            </div>
          )}
          {a.income_limit_near > 0 && (
            <div style={{ ...h.signal, background:'#eff6ff', borderColor:'#bfdbfe', color:'#1e40af' }}>
              📊 <b>{a.income_limit_near} исполнителя</b> близко к лимиту дохода 2 400 000 ₽
            </div>
          )}
        </div>
      )}

      {/* ── Вкладки ── */}
      <div style={h.tabs}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{ ...h.tab, ...(activeTab === tab.id ? h.tabActive : {}) }}
          >{tab.label}</button>
        ))}
      </div>

      {/* ── Контент вкладки ── */}
      <div style={h.tabContent}>
        {activeTab === 'executors'  && <ExecutorsTab />}
        {activeTab === 'documents'  && <DocumentsTab />}
        {activeTab === 'payments'   && <PaymentsTab />}
        {activeTab === 'analytics'  && <AnalyticsTab />}
      </div>

    </div>
  )
}

// ─── Стили ────────────────────────────────────────────────────────────────
const h = {
  header:         { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:16 },
  pageTitle:      { fontSize:22, fontWeight:800, color:'#111827', margin:0 },
  pageSubtitle:   { fontSize:13, color:'#6b7280', margin:'4px 0 0' },
  demoBadge:      { background:'#fef3c7', color:'#92400e', fontSize:11, fontWeight:700, padding:'4px 10px', borderRadius:6, flexShrink:0 },
  signalsRow:     { display:'flex', flexDirection:'column', gap:8, marginBottom:20 },
  signal:         { background:'#fffbeb', border:'1px solid #fde68a', borderRadius:8, padding:'10px 16px', fontSize:13, color:'#92400e' },
  tabs:           { display:'flex', gap:4, marginBottom:0, borderBottom:'2px solid #e5e7eb' },
  tab:            { padding:'10px 18px', fontSize:13, fontWeight:600, color:'#6b7280', background:'transparent', border:'none', cursor:'pointer', borderRadius:'6px 6px 0 0', fontFamily:'inherit' },
  tabActive:      { color:'#A01F72', background:'#fdf4fb', borderBottom:'2px solid #A01F72', marginBottom:-2 },
  tabContent:     { background:'#fff', border:'1.5px solid #e5e7eb', borderTop:'none', borderRadius:'0 0 12px 12px', padding:'20px' },
  filterRow:      { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16, flexWrap:'wrap', gap:10 },
  searchInput:    { border:'1.5px solid #d1d5db', borderRadius:8, padding:'7px 12px', fontSize:13, fontFamily:'inherit', outline:'none', width:280 },
  filterBtns:     { display:'flex', gap:6 },
  filterBtn:      { padding:'6px 14px', fontSize:12, fontWeight:600, color:'#6b7280', background:'#f3f4f6', border:'none', borderRadius:6, cursor:'pointer', fontFamily:'inherit' },
  filterBtnActive:{ background:'#A01F72', color:'#fff' },
  tableWrap:      { overflowX:'auto' },
  table:          { width:'100%', borderCollapse:'collapse' },
  thead:          { background:'#f9fafb' },
  th:             { padding:'10px 12px', fontSize:11, fontWeight:700, color:'#6b7280', textAlign:'left', borderBottom:'1.5px solid #e5e7eb', whiteSpace:'nowrap' },
  tr:             { borderBottom:'1px solid #f3f4f6' },
  td:             { padding:'10px 12px', fontSize:13, color:'#374151', verticalAlign:'middle' },
  exName:         { fontWeight:700, color:'#111827' },
  exMeta:         { fontSize:11, color:'#9ca3af', marginTop:2 },
  storeName:      { fontSize:12, background:'#f3f4f6', padding:'2px 8px', borderRadius:6, fontWeight:600 },
  incomeRow:      { display:'flex', justifyContent:'space-between', marginBottom:4 },
  riskBadge:      { fontSize:10, fontWeight:700, color:'#dc2626', background:'#fef2f2', padding:'1px 5px', borderRadius:5 },
  monoText:       { fontFamily:'monospace', fontSize:11, color:'#6b7280' },
  typeChip:       { background:'#eff6ff', color:'#1d4ed8', fontSize:11, fontWeight:700, padding:'2px 8px', borderRadius:8 },
  empty:          { textAlign:'center', padding:'32px', color:'#9ca3af', fontSize:13 },
  miniCard:       { background:'#f9fafb', border:'1px solid #e5e7eb', borderRadius:10, padding:'12px 14px' },
  miniLabel:      { fontSize:11, color:'#6b7280', fontWeight:600, marginBottom:4 },
  miniVal:        { fontSize:20, fontWeight:800 },
  analyticsCard:  { background:'#f9fafb', border:'1.5px solid #e5e7eb', borderRadius:12, padding:'16px 18px' },
  analyticsTitle: { fontSize:13, fontWeight:800, color:'#242D4A', marginBottom:12 },
  analyticsRow:   { display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid #e5e7eb' },
  analyticsLabel: { fontSize:12, color:'#6b7280' },
  analyticsVal:   { fontSize:13, fontWeight:700, color:'#111827' },
}
