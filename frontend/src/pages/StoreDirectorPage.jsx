// =============================================================================
// KARI.Самозанятые — Кабинет директора магазина
// =============================================================================
// Директор магазина:
//   - Видит задания своего магазина
//   - Создаёт задания
//   - Принимает или отклоняет сданные работы (с фотоотчётом)
//   - Видит бюджет магазина и активных исполнителей

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { tasksAPI }    from '../api/client.js'

// ─── Демо-данные (пока бэкенд не поднят) ──────────────────────────────────
const DEMO_STORE = {
  name: 'ТЦ «Карамель»',
  address: 'г. Иркутск, ул. Байкальская, 253А',
  budget_total: 300_000,
  budget_used:  126_000,
  executors_active: 7,
}

const DEMO_TASKS = [
  { id:'t1', number:'ТЗ-2026-000041', title:'Уборка торгового зала', category:'cleaning',
    status:'submitted', executor_name:'Иванов И.И.', price:1500, scheduled_date:'2026-04-01',
    submitted_at:'2026-04-01T14:22:00Z', photos:['/demo/photo1.jpg'] },
  { id:'t2', number:'ТЗ-2026-000042', title:'Выкладка весенней коллекции', category:'merchandising',
    status:'submitted', executor_name:'Сидорова А.В.', price:2200, scheduled_date:'2026-04-01',
    submitted_at:'2026-04-01T16:05:00Z', photos:[] },
  { id:'t3', number:'ТЗ-2026-000039', title:'Инвентаризация склада', category:'inventory',
    status:'in_progress', executor_name:'Петров В.С.', price:3000, scheduled_date:'2026-04-02',
    submitted_at: null, photos:[] },
  { id:'t4', number:'ТЗ-2026-000038', title:'Разгрузка товара', category:'unloading',
    status:'completed', executor_name:'Козлов М.Р.', price:1800, scheduled_date:'2026-03-31',
    submitted_at:'2026-03-31T12:00:00Z', photos:[] },
  { id:'t5', number:'ТЗ-2026-000040', title:'Промо-акция у входа', category:'promotion',
    status:'published', executor_name: null, price:2500, scheduled_date:'2026-04-03',
    submitted_at: null, photos:[] },
  { id:'t6', number:'ТЗ-2026-000043', title:'Обновление ценников', category:'marking',
    status:'draft', executor_name: null, price:900, scheduled_date:'2026-04-04',
    submitted_at: null, photos:[] },
]

const STATUS_META = {
  draft:       { label:'Черновик',       color:'#6b7280', bg:'#f3f4f6' },
  published:   { label:'На бирже',       color:'#2563eb', bg:'#eff6ff' },
  taken:       { label:'Взято',          color:'#7c3aed', bg:'#f5f3ff' },
  in_progress: { label:'В работе',       color:'#d97706', bg:'#fffbeb' },
  submitted:   { label:'На проверке',    color:'#ea580c', bg:'#fff7ed' },
  accepted:    { label:'Принято',        color:'#16a34a', bg:'#f0fdf4' },
  completed:   { label:'Завершено',      color:'#16a34a', bg:'#f0fdf4' },
  rejected:    { label:'Отклонено',      color:'#dc2626', bg:'#fef2f2' },
  cancelled:   { label:'Отменено',       color:'#9ca3af', bg:'#f9fafb' },
}

const CATEGORY_LABELS = {
  cleaning:'Уборка', merchandising:'Выкладка', inventory:'Инвентаризация',
  unloading:'Разгрузка', promotion:'Промо', marking:'Ценники', other:'Прочее',
}

const TABS = [
  { id:'submitted',   label:'На проверке',  filter: t => t.status === 'submitted' },
  { id:'active',      label:'Активные',     filter: t => ['published','taken','in_progress'].includes(t.status) },
  { id:'completed',   label:'Завершённые',  filter: t => ['completed','accepted'].includes(t.status) },
  { id:'all',         label:'Все',          filter: () => true },
]

// ─── Компоненты ──────────────────────────────────────────────────────────────

function ProgressBar({ value }) {
  const pct = Math.min(100, value)
  const color = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981'
  return (
    <div style={{ background:'#e5e7eb', borderRadius:4, height:8, overflow:'hidden' }}>
      <div style={{ width:`${pct}%`, height:'100%', background:color, transition:'width .4s', borderRadius:4 }} />
    </div>
  )
}

function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.draft
  return (
    <span style={{ background:m.bg, color:m.color, fontSize:11, fontWeight:700,
      padding:'2px 8px', borderRadius:10, whiteSpace:'nowrap' }}>
      {m.label}
    </span>
  )
}

// ─── Модальное окно: приёмка / отклонение ─────────────────────────────────

function AcceptModal({ task, onClose, onAccept, onReject }) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason]       = useState('')
  const [loading, setLoading]     = useState(false)

  const handleAccept = async () => {
    setLoading(true)
    await onAccept(task.id)
    setLoading(false)
    onClose()
  }

  const handleReject = async () => {
    if (!reason.trim()) return
    setLoading(true)
    await onReject(task.id, reason)
    setLoading(false)
    onClose()
  }

  return (
    <div style={ms.overlay} onClick={onClose}>
      <div style={ms.modal} onClick={e => e.stopPropagation()}>
        <div style={ms.header}>
          <h3 style={ms.title}>Приёмка работы</h3>
          <button onClick={onClose} style={ms.closeBtn}>✕</button>
        </div>

        <div style={ms.body}>
          {/* Информация о задании */}
          <div style={ms.infoRow}>
            <span style={ms.infoLabel}>Задание</span>
            <span style={ms.infoVal}>{task.title}</span>
          </div>
          <div style={ms.infoRow}>
            <span style={ms.infoLabel}>Исполнитель</span>
            <span style={ms.infoVal}>{task.executor_name}</span>
          </div>
          <div style={ms.infoRow}>
            <span style={ms.infoLabel}>Сумма</span>
            <span style={{ ...ms.infoVal, color:'#A01F72', fontWeight:700 }}>
              {task.price.toLocaleString('ru-RU')} ₽
            </span>
          </div>

          {/* Фотоотчёт */}
          {task.photos?.length > 0 ? (
            <div style={ms.photosSection}>
              <div style={ms.photosLabel}>📷 Фотоотчёт ({task.photos.length} фото)</div>
              <div style={ms.photosGrid}>
                {task.photos.map((url, i) => (
                  <div key={i} style={ms.photoThumb}>
                    <div style={ms.photoPlaceholder}>🖼</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={ms.noPhoto}>
              <span style={{ fontSize:24 }}>📷</span>
              <span style={{ color:'#9ca3af', fontSize:13 }}>Фотоотчёт не прикреплён</span>
            </div>
          )}

          {/* Форма отклонения */}
          {rejecting && (
            <div style={ms.rejectForm}>
              <label style={ms.rejectLabel}>Причина отклонения *</label>
              <textarea
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Опишите что именно не так..."
                rows={3}
                style={ms.rejectTextarea}
              />
            </div>
          )}
        </div>

        <div style={ms.footer}>
          {!rejecting ? (
            <>
              <button
                onClick={() => setRejecting(true)}
                style={{ ...ms.btn, ...ms.btnReject }}
              >✕ Отклонить</button>
              <button
                onClick={handleAccept}
                disabled={loading}
                style={{ ...ms.btn, ...ms.btnAccept }}
              >{loading ? '...' : '✓ Принять работу'}</button>
            </>
          ) : (
            <>
              <button
                onClick={() => setRejecting(false)}
                style={{ ...ms.btn, background:'#f3f4f6', color:'#374151' }}
              >← Назад</button>
              <button
                onClick={handleReject}
                disabled={!reason.trim() || loading}
                style={{ ...ms.btn, ...ms.btnReject, opacity: !reason.trim() ? .5 : 1 }}
              >{loading ? '...' : 'Отклонить →'}</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Модальное окно: создать задание ──────────────────────────────────────

function CreateTaskModal({ onClose, onSave }) {
  const [form, setForm] = useState({
    title:'', category:'cleaning', description:'', price:'', scheduled_date:'',
    required_photo_count: 1,
  })
  const [loading, setLoading] = useState(false)

  const handleSave = async () => {
    if (!form.title || !form.price || !form.scheduled_date) return
    setLoading(true)
    await onSave(form)
    setLoading(false)
    onClose()
  }

  const field = (key, val) => setForm(f => ({ ...f, [key]: val }))

  return (
    <div style={ms.overlay} onClick={onClose}>
      <div style={{ ...ms.modal, maxWidth:520 }} onClick={e => e.stopPropagation()}>
        <div style={ms.header}>
          <h3 style={ms.title}>Новое задание</h3>
          <button onClick={onClose} style={ms.closeBtn}>✕</button>
        </div>
        <div style={ms.body}>
          {[
            ['Название *', 'title', 'text', 'Напр.: Уборка торгового зала'],
            ['Стоимость (₽) *', 'price', 'number', '1500'],
            ['Дата выполнения *', 'scheduled_date', 'date', ''],
          ].map(([label, key, type, ph]) => (
            <div key={key} style={{ marginBottom:14 }}>
              <label style={ms.fieldLabel}>{label}</label>
              <input
                type={type}
                value={form[key]}
                onChange={e => field(key, e.target.value)}
                placeholder={ph}
                style={ms.input}
              />
            </div>
          ))}

          <div style={{ marginBottom:14 }}>
            <label style={ms.fieldLabel}>Категория *</label>
            <select value={form.category} onChange={e => field('category', e.target.value)} style={ms.input}>
              {Object.entries(CATEGORY_LABELS).map(([v,l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom:14 }}>
            <label style={ms.fieldLabel}>Описание задания</label>
            <textarea
              value={form.description}
              onChange={e => field('description', e.target.value)}
              placeholder="Подробно опишите что нужно сделать..."
              rows={3}
              style={{ ...ms.input, resize:'vertical' }}
            />
          </div>

          <div>
            <label style={ms.fieldLabel}>Количество фото при сдаче</label>
            <select value={form.required_photo_count} onChange={e => field('required_photo_count', +e.target.value)} style={ms.input}>
              <option value={1}>1 фото (минимум)</option>
              <option value={2}>2 фото</option>
              <option value={3}>3 фото (максимум)</option>
            </select>
          </div>
        </div>
        <div style={ms.footer}>
          <button onClick={onClose} style={{ ...ms.btn, background:'#f3f4f6', color:'#374151' }}>Отмена</button>
          <button
            onClick={handleSave}
            disabled={!form.title || !form.price || !form.scheduled_date || loading}
            style={{ ...ms.btn, ...ms.btnAccept, opacity: (!form.title||!form.price||!form.scheduled_date) ? .5 : 1 }}
          >{loading ? 'Создаём...' : '+ Создать задание'}</button>
        </div>
      </div>
    </div>
  )
}

// ─── Главный компонент ─────────────────────────────────────────────────────

export default function StoreDirectorPage() {
  const [tasks, setTasks]         = useState(DEMO_TASKS)
  const [activeTab, setActiveTab] = useState('submitted')
  const [selected, setSelected]   = useState(null)   // задание для приёмки
  const [creating, setCreating]   = useState(false)

  const budgetPct = Math.round(DEMO_STORE.budget_used / DEMO_STORE.budget_total * 100)

  const handleAccept = async (taskId) => {
    setTasks(ts => ts.map(t => t.id === taskId ? { ...t, status:'completed' } : t))
  }
  const handleReject = async (taskId, reason) => {
    setTasks(ts => ts.map(t => t.id === taskId ? { ...t, status:'rejected' } : t))
  }
  const handleCreate = async (form) => {
    const newTask = {
      id: 't' + Date.now(),
      number: 'ТЗ-2026-' + String(Math.floor(Math.random()*9000+1000)).padStart(6,'0'),
      title: form.title,
      category: form.category,
      status: 'draft',
      executor_name: null,
      price: +form.price,
      scheduled_date: form.scheduled_date,
      submitted_at: null,
      photos: [],
    }
    setTasks(ts => [newTask, ...ts])
  }

  const currentTab = TABS.find(t => t.id === activeTab)
  const filtered   = tasks.filter(currentTab.filter)
  const pendingCount = tasks.filter(t => t.status === 'submitted').length

  return (
    <div style={{ fontFamily:'Nunito,sans-serif', maxWidth:900 }}>

      {/* ── Шапка ── */}
      <div style={s.header}>
        <div>
          <h1 style={s.pageTitle}>{DEMO_STORE.name}</h1>
          <p style={s.pageSubtitle}>{DEMO_STORE.address}</p>
        </div>
        <div style={{ display:'flex', gap:10, alignItems:'center' }}>
          <span style={s.demoBadge}>🛠 Демо</span>
          <button onClick={() => setCreating(true)} style={s.btnPrimary}>
            + Создать задание
          </button>
        </div>
      </div>

      {/* ── Метрики ── */}
      <div style={s.metrics}>
        <div style={s.metricCard}>
          <div style={s.metricLabel}>Бюджет месяца</div>
          <div style={s.metricValue}>{DEMO_STORE.budget_used.toLocaleString('ru-RU')} ₽</div>
          <div style={{ marginTop:8 }}>
            <ProgressBar value={budgetPct} />
          </div>
          <div style={s.metricSub}>{budgetPct}% из {DEMO_STORE.budget_total.toLocaleString('ru-RU')} ₽</div>
        </div>

        <div style={s.metricCard}>
          <div style={s.metricLabel}>Исполнителей</div>
          <div style={s.metricValue}>{DEMO_STORE.executors_active}</div>
          <div style={s.metricSub}>активных сейчас</div>
        </div>

        <div style={{ ...s.metricCard, borderColor: pendingCount > 0 ? '#f59e0b' : '#e5e7eb',
          background: pendingCount > 0 ? '#fffbeb' : '#fff' }}>
          <div style={s.metricLabel}>На проверке</div>
          <div style={{ ...s.metricValue, color: pendingCount > 0 ? '#d97706' : '#111' }}>
            {pendingCount}
          </div>
          <div style={s.metricSub}>
            {pendingCount > 0 ? '⚠️ Ждут вашей приёмки' : 'Всё проверено'}
          </div>
        </div>

        <div style={s.metricCard}>
          <div style={s.metricLabel}>Заданий сегодня</div>
          <div style={s.metricValue}>{tasks.filter(t => t.status !== 'cancelled').length}</div>
          <div style={s.metricSub}>
            {tasks.filter(t => t.status === 'completed').length} завершено
          </div>
        </div>
      </div>

      {/* ── Вкладки ── */}
      <div style={s.tabs}>
        {TABS.map(tab => {
          const cnt = tasks.filter(tab.filter).length
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{ ...s.tab, ...(activeTab === tab.id ? s.tabActive : {}) }}
            >
              {tab.label}
              {cnt > 0 && (
                <span style={{ ...s.tabBadge, background: tab.id === 'submitted' && cnt > 0 ? '#f59e0b' : '#e5e7eb',
                  color: tab.id === 'submitted' && cnt > 0 ? '#fff' : '#6b7280' }}>
                  {cnt}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* ── Список заданий ── */}
      {filtered.length === 0 ? (
        <div style={s.empty}>Заданий нет</div>
      ) : (
        <div style={s.taskList}>
          {filtered.map(task => (
            <div key={task.id} style={s.taskRow}>
              <div style={s.taskMain}>
                <div style={s.taskNumber}>{task.number}</div>
                <div style={s.taskTitle}>{task.title}</div>
                <div style={s.taskMeta}>
                  <span style={s.taskCategory}>{CATEGORY_LABELS[task.category]}</span>
                  <span style={s.taskDot}>·</span>
                  <span>{task.scheduled_date}</span>
                  {task.executor_name && (
                    <>
                      <span style={s.taskDot}>·</span>
                      <span>👤 {task.executor_name}</span>
                    </>
                  )}
                </div>
              </div>

              <div style={s.taskRight}>
                <div style={s.taskPrice}>{task.price.toLocaleString('ru-RU')} ₽</div>
                <StatusBadge status={task.status} />
                {task.status === 'submitted' && (
                  <button
                    onClick={() => setSelected(task)}
                    style={s.btnAcceptSmall}
                  >Проверить →</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Модалки ── */}
      {selected && (
        <AcceptModal
          task={selected}
          onClose={() => setSelected(null)}
          onAccept={handleAccept}
          onReject={handleReject}
        />
      )}
      {creating && (
        <CreateTaskModal
          onClose={() => setCreating(false)}
          onSave={handleCreate}
        />
      )}
    </div>
  )
}

// ─── Стили ────────────────────────────────────────────────────────────────
const s = {
  header:      { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:24 },
  pageTitle:   { fontSize:22, fontWeight:800, color:'#111827', margin:0 },
  pageSubtitle:{ fontSize:13, color:'#6b7280', margin:'4px 0 0' },
  demoBadge:   { background:'#fef3c7', color:'#92400e', fontSize:11, fontWeight:700, padding:'4px 10px', borderRadius:6 },
  btnPrimary:  { background:'#A01F72', color:'#fff', border:'none', borderRadius:8, padding:'9px 18px', fontSize:13, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },

  metrics:     { display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:24 },
  metricCard:  { background:'#fff', border:'1.5px solid #e5e7eb', borderRadius:12, padding:'16px 18px' },
  metricLabel: { fontSize:12, color:'#6b7280', fontWeight:600, marginBottom:4 },
  metricValue: { fontSize:26, fontWeight:800, color:'#111827' },
  metricSub:   { fontSize:11, color:'#9ca3af', marginTop:6 },

  tabs:        { display:'flex', gap:4, marginBottom:16, borderBottom:'2px solid #e5e7eb', paddingBottom:0 },
  tab:         { padding:'8px 16px', fontSize:13, fontWeight:600, color:'#6b7280', background:'transparent', border:'none', cursor:'pointer', borderRadius:'6px 6px 0 0', display:'flex', alignItems:'center', gap:6, fontFamily:'inherit' },
  tabActive:   { color:'#A01F72', background:'#fdf4fb', borderBottom:'2px solid #A01F72', marginBottom:-2 },
  tabBadge:    { fontSize:11, fontWeight:700, padding:'1px 6px', borderRadius:10 },

  taskList:    { display:'flex', flexDirection:'column', gap:8 },
  taskRow:     { background:'#fff', border:'1.5px solid #e5e7eb', borderRadius:10, padding:'14px 18px', display:'flex', justifyContent:'space-between', alignItems:'center', gap:16 },
  taskMain:    { flex:1, minWidth:0 },
  taskNumber:  { fontSize:11, color:'#9ca3af', fontWeight:600, marginBottom:2 },
  taskTitle:   { fontSize:14, fontWeight:700, color:'#111827' },
  taskMeta:    { display:'flex', gap:8, fontSize:12, color:'#6b7280', marginTop:4, flexWrap:'wrap' },
  taskCategory:{ background:'#f3f4f6', color:'#374151', padding:'1px 7px', borderRadius:6, fontSize:11, fontWeight:600 },
  taskDot:     { color:'#d1d5db' },
  taskRight:   { display:'flex', flexDirection:'column', alignItems:'flex-end', gap:6, flexShrink:0 },
  taskPrice:   { fontSize:15, fontWeight:800, color:'#A01F72' },
  btnAcceptSmall:{ background:'#fff7ed', color:'#ea580c', border:'1px solid #fed7aa', borderRadius:6, padding:'5px 12px', fontSize:12, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
  empty:       { textAlign:'center', padding:'48px 0', color:'#9ca3af', fontSize:14 },
}

// Стили модального окна
const ms = {
  overlay:     { position:'fixed', inset:0, background:'rgba(0,0,0,.45)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center', padding:20 },
  modal:       { background:'#fff', borderRadius:16, width:'100%', maxWidth:480, boxShadow:'0 20px 60px rgba(0,0,0,.2)', maxHeight:'90vh', overflow:'auto' },
  header:      { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'20px 24px 0' },
  title:       { fontSize:16, fontWeight:800, color:'#111827', margin:0 },
  closeBtn:    { background:'none', border:'none', fontSize:18, cursor:'pointer', color:'#6b7280', lineHeight:1 },
  body:        { padding:'16px 24px' },
  footer:      { padding:'16px 24px', borderTop:'1px solid #f3f4f6', display:'flex', gap:10, justifyContent:'flex-end' },
  btn:         { padding:'9px 18px', borderRadius:8, border:'none', fontSize:13, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
  btnAccept:   { background:'#A01F72', color:'#fff' },
  btnReject:   { background:'#fef2f2', color:'#dc2626', border:'1px solid #fecaca' },
  infoRow:     { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'8px 0', borderBottom:'1px solid #f3f4f6' },
  infoLabel:   { fontSize:12, color:'#6b7280', fontWeight:600 },
  infoVal:     { fontSize:13, fontWeight:700, color:'#111827' },
  photosSection:{ marginTop:16 },
  photosLabel: { fontSize:12, fontWeight:700, color:'#374151', marginBottom:8 },
  photosGrid:  { display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8 },
  photoThumb:  { aspectRatio:'1', background:'#f3f4f6', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center' },
  photoPlaceholder:{ fontSize:24 },
  noPhoto:     { display:'flex', flexDirection:'column', alignItems:'center', gap:8, padding:'20px 0', color:'#9ca3af' },
  rejectForm:  { marginTop:16 },
  rejectLabel: { fontSize:12, fontWeight:700, color:'#374151', display:'block', marginBottom:6 },
  rejectTextarea:{ width:'100%', border:'1.5px solid #d1d5db', borderRadius:8, padding:'8px 12px', fontSize:13, fontFamily:'inherit', resize:'vertical', boxSizing:'border-box', outline:'none' },
  fieldLabel:  { fontSize:12, fontWeight:700, color:'#374151', display:'block', marginBottom:5 },
  input:       { width:'100%', border:'1.5px solid #d1d5db', borderRadius:8, padding:'8px 12px', fontSize:13, fontFamily:'inherit', outline:'none', boxSizing:'border-box' },
}
