// =============================================================================
// KARI.Самозанятые — Страница «Задания» (кабинет директора региона)
// =============================================================================
//
// Функции:
//  - Список заданий с фильтрацией по статусу
//  - Кнопки «Опубликовать» (из черновика) и «Отменить»
//  - Модальное окно создания нового задания
//  - Пагинация

import { useState, useEffect, useCallback } from 'react'
import { tasksAPI } from '../api/client.js'
import { DEMO_TASKS } from '../api/demo.js'

// Цветовые метки статусов
const TASK_STATUSES = {
  draft:          { label: 'Черновик',       color: '#374151', bg: '#f3f4f6' },
  published:      { label: 'Опубликовано',   color: '#1d4ed8', bg: '#eff6ff' },
  in_progress:    { label: 'Выполняется',    color: '#92400e', bg: '#fef3c7' },
  pending_review: { label: 'На проверке',    color: '#5b21b6', bg: '#ede9fe' },
  completed:      { label: 'Завершено',      color: '#065f46', bg: '#d1fae5' },
  cancelled:      { label: 'Отменено',       color: '#991b1b', bg: '#fee2e2' },
}

// Фильтры по статусу
const STATUS_FILTERS = [
  { value: '',               label: 'Все'           },
  { value: 'draft',          label: 'Черновики'     },
  { value: 'published',      label: 'Опубликованные'},
  { value: 'in_progress',    label: 'Выполняются'   },
  { value: 'pending_review', label: 'На проверке'   },
  { value: 'completed',      label: 'Завершённые'   },
  { value: 'cancelled',      label: 'Отменённые'    },
]

// Категории заданий
const CATEGORIES = {
  cleaning:  'Уборка',
  delivery:  'Доставка',
  assembly:  'Сборка',
  loading:   'Погрузка',
  promotion: 'Промоакция',
  inventory: 'Инвентаризация',
  other:     'Другое',
}

export default function TasksPage() {
  const [tasks,      setTasks]      = useState([])
  const [total,      setTotal]      = useState(0)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [status,     setStatus]     = useState('')
  const [page,       setPage]       = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const [actionId,   setActionId]   = useState(null)  // ID задания, по которому идёт действие

  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await tasksAPI.getList({
        status: status || undefined,
        skip:   (page - 1) * PAGE_SIZE,
        limit:  PAGE_SIZE,
      })
      const items = data.items ?? data
      const arr   = Array.isArray(items) ? items : []
      if (arr.length === 0) throw new Error('empty')
      setTasks(arr)
      setTotal(data.total ?? arr.length)
    } catch {
      // Бэкенд недоступен или нет данных — показываем демо-данные
      const filtered = status
        ? DEMO_TASKS.items.filter(t => t.status === status)
        : DEMO_TASKS.items
      setTasks(filtered)
      setTotal(DEMO_TASKS.total)
    } finally {
      setLoading(false)
    }
  }, [status, page])

  useEffect(() => { load() }, [load])

  // Опубликовать или отменить задание
  const handleAction = async (taskId, action) => {
    setActionId(taskId)
    setError('')
    try {
      if (action === 'publish') await tasksAPI.publish(taskId)
      if (action === 'cancel')  await tasksAPI.cancel(taskId)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка при выполнении действия')
    } finally {
      setActionId(null)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>

      {/* Заголовок */}
      <div style={styles.pageHeader}>
        <div>
          <h1 style={styles.pageTitle}>Задания</h1>
          <p style={styles.pageSubtitle}>Всего заданий: <strong>{loading ? '...' : total}</strong></p>
        </div>
        <button style={styles.btnPrimary} onClick={() => setShowCreate(true)}>
          ➕ Создать задание
        </button>
      </div>

      {/* Фильтр-таблетки по статусу */}
      <div style={styles.filterRow}>
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            style={{
              ...styles.filterTab,
              ...(status === f.value ? styles.filterTabActive : {}),
            }}
            onClick={() => { setStatus(f.value); setPage(1) }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Ошибка */}
      {error && <div style={styles.errorBox}>{error}</div>}

      {/* ===== Таблица ===== */}
      <div style={styles.tableWrap}>
        {loading ? (
          <div style={styles.placeholder}>Загрузка...</div>
        ) : tasks.length === 0 ? (
          <div style={styles.placeholder}>
            {status
              ? `Заданий со статусом «${STATUS_FILTERS.find(f => f.value === status)?.label}» нет`
              : 'Заданий пока нет'}
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Задание</th>
                <th style={styles.th}>Магазин</th>
                <th style={styles.th}>Исполнитель</th>
                <th style={styles.th}>Статус</th>
                <th style={styles.th}>Сумма</th>
                <th style={styles.th}>Дата</th>
                <th style={styles.th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => {
                const st   = TASK_STATUSES[t.status] || TASK_STATUSES.draft
                const busy = actionId === t.id

                return (
                  <tr key={t.id} style={styles.tr}>

                    {/* Название + категория */}
                    <td style={styles.td}>
                      <div style={styles.taskTitle}>{t.title}</div>
                      {t.category && (
                        <div style={styles.taskCat}>
                          {CATEGORIES[t.category] || t.category}
                        </div>
                      )}
                    </td>

                    {/* Магазин */}
                    <td style={styles.td}>
                      <span style={styles.secondary}>{t.store_name || '—'}</span>
                    </td>

                    {/* Исполнитель */}
                    <td style={styles.td}>
                      {t.executor_name
                        ? <span style={styles.secondary}>{t.executor_name}</span>
                        : <span style={styles.muted}>Не назначен</span>
                      }
                    </td>

                    {/* Статус */}
                    <td style={styles.td}>
                      <span style={{ ...styles.badge, color: st.color, background: st.bg }}>
                        {st.label}
                      </span>
                    </td>

                    {/* Сумма */}
                    <td style={styles.td}>
                      <span style={styles.amount}>
                        {t.amount != null ? formatMoney(t.amount) : '—'}
                      </span>
                    </td>

                    {/* Дата */}
                    <td style={styles.td}>
                      <span style={styles.date}>{formatDate(t.created_at)}</span>
                    </td>

                    {/* Действия */}
                    <td style={styles.td}>
                      <div style={styles.actionsCell}>
                        {/* Опубликовать (только черновики) */}
                        {t.status === 'draft' && (
                          <button
                            style={{ ...styles.btnAct, ...styles.btnPublish }}
                            onClick={() => handleAction(t.id, 'publish')}
                            disabled={busy}
                          >
                            {busy ? '...' : '▶ Опубликовать'}
                          </button>
                        )}
                        {/* Отменить (черновики и опубликованные) */}
                        {['draft', 'published'].includes(t.status) && (
                          <button
                            style={{ ...styles.btnAct, ...styles.btnCancel }}
                            onClick={() => handleAction(t.id, 'cancel')}
                            disabled={busy}
                          >
                            {busy ? '...' : '✕ Отменить'}
                          </button>
                        )}
                      </div>
                    </td>

                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Пагинация */}
      {totalPages > 1 && (
        <div style={styles.pagination}>
          <button
            style={styles.pageBtn}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            ← Назад
          </button>
          <span style={styles.pageInfo}>Страница {page} из {totalPages}</span>
          <button
            style={styles.pageBtn}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Вперёд →
          </button>
        </div>
      )}

      {/* Модальное окно создания задания */}
      {showCreate && (
        <CreateTaskModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load() }}
        />
      )}

    </div>
  )
}

// =============================================================================
// Модальное окно «Создать задание»
// =============================================================================
function CreateTaskModal({ onClose, onCreated }) {
  const [form,    setForm]    = useState({
    title: '', description: '', amount: '', store_name: '', category: 'cleaning',
  })
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  // Обновить одно поле формы
  const setField = (key, val) => setForm(f => ({ ...f, [key]: val }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await tasksAPI.create({
        ...form,
        amount: parseFloat(form.amount),
      })
      onCreated()
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка создания задания')
    } finally {
      setLoading(false)
    }
  }

  // Закрыть по клику на затемнение
  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div style={modal.overlay} onClick={handleOverlayClick}>
      <div style={modal.box}>

        {/* Шапка */}
        <div style={modal.header}>
          <h2 style={modal.title}>Новое задание</h2>
          <button style={modal.closeBtn} onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        <form onSubmit={handleSubmit} style={modal.form}>

          <div style={modal.row}>
            <label style={modal.label}>Название задания *</label>
            <input
              style={modal.input}
              value={form.title}
              onChange={e => setField('title', e.target.value)}
              placeholder="Например: Уборка торгового зала"
              required
            />
          </div>

          <div style={modal.row2}>
            <div style={modal.col}>
              <label style={modal.label}>Магазин</label>
              <input
                style={modal.input}
                value={form.store_name}
                onChange={e => setField('store_name', e.target.value)}
                placeholder="Адрес или название"
              />
            </div>
            <div style={modal.col}>
              <label style={modal.label}>Категория</label>
              <select
                style={modal.input}
                value={form.category}
                onChange={e => setField('category', e.target.value)}
              >
                {Object.entries(CATEGORIES).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={modal.row}>
            <label style={modal.label}>Описание задания</label>
            <textarea
              style={{ ...modal.input, height: '90px', resize: 'vertical' }}
              value={form.description}
              onChange={e => setField('description', e.target.value)}
              placeholder="Подробно опишите что нужно сделать..."
            />
          </div>

          <div style={modal.row}>
            <label style={modal.label}>Сумма выплаты (₽) *</label>
            <input
              style={modal.input}
              type="number"
              min="100"
              max="100000"
              step="50"
              value={form.amount}
              onChange={e => setField('amount', e.target.value)}
              placeholder="1 500"
              required
            />
            <div style={modal.hint}>
              Минимум 100 ₽ · KARI компенсирует 6% налог самозанятому
            </div>
          </div>

          {error && <div style={modal.error}>{error}</div>}

          <div style={modal.footer}>
            <button type="button" style={modal.btnCancel} onClick={onClose}>
              Отмена
            </button>
            <button
              type="submit"
              style={loading ? { ...modal.btnSave, opacity: .6 } : modal.btnSave}
              disabled={loading}
            >
              {loading ? 'Создаём...' : 'Создать задание'}
            </button>
          </div>

        </form>
      </div>
    </div>
  )
}

// Утилиты форматирования
function formatMoney(v) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency', currency: 'RUB', maximumFractionDigits: 0,
  }).format(v)
}

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('ru-RU', {
    day: '2-digit', month: '2-digit', year: '2-digit',
  })
}

// ===== Стили страницы =====
const styles = {
  pageHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: '20px',
    gap: '16px',
    flexWrap: 'wrap',
  },
  pageTitle:    { fontSize: '26px', fontWeight: '800', color: '#1a1a1a', margin: 0 },
  pageSubtitle: { fontSize: '14px', color: '#6b7280', marginTop: '4px', marginBottom: 0 },
  btnPrimary: {
    background: '#a91d7a',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 18px',
    fontSize: '13px',
    fontWeight: '700',
    fontFamily: 'inherit',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  filterRow: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
    marginBottom: '20px',
  },
  filterTab: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '20px',
    padding: '5px 14px',
    fontSize: '12px',
    fontWeight: '700',
    color: '#6b7280',
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  filterTabActive: {
    background: '#a91d7a',
    color: '#fff',
    borderColor: '#a91d7a',
  },
  errorBox: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    padding: '12px 16px',
    fontSize: '13px',
    color: '#dc2626',
    marginBottom: '16px',
  },
  tableWrap: {
    background: '#fff',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
    overflow: 'hidden',
  },
  placeholder: {
    padding: '56px',
    textAlign: 'center',
    color: '#9ca3af',
    fontSize: '14px',
  },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: {
    padding: '12px 16px',
    textAlign: 'left',
    fontSize: '11px',
    fontWeight: '700',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '.05em',
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
  },
  tr:  { borderBottom: '1px solid #f5f5f5' },
  td:  { padding: '13px 16px', verticalAlign: 'middle' },
  taskTitle: { fontSize: '14px', fontWeight: '600', color: '#1a1a1a' },
  taskCat:   { fontSize: '11px', color: '#9ca3af', marginTop: '2px', textTransform: 'uppercase', letterSpacing: '.04em' },
  secondary: { fontSize: '13px', color: '#374151' },
  muted:     { fontSize: '13px', color: '#9ca3af' },
  badge:     { display: 'inline-block', padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '700' },
  amount:    { fontSize: '13px', fontWeight: '700', color: '#1a1a1a' },
  date:      { fontSize: '12px', color: '#6b7280' },
  actionsCell: { display: 'flex', gap: '6px', flexWrap: 'wrap' },
  btnAct:    { border: 'none', borderRadius: '6px', padding: '5px 10px', fontSize: '12px', fontWeight: '700', fontFamily: 'inherit', cursor: 'pointer' },
  btnPublish: { background: '#dbeafe', color: '#1d4ed8' },
  btnCancel:  { background: '#fee2e2', color: '#dc2626' },
  pagination: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', marginTop: '20px' },
  pageBtn:   { background: '#fff', border: '1px solid #e5e7eb', borderRadius: '6px', padding: '7px 16px', fontSize: '13px', fontWeight: '600', fontFamily: 'inherit', cursor: 'pointer', color: '#374151' },
  pageInfo:  { fontSize: '13px', color: '#6b7280' },
}

// ===== Стили модального окна =====
const modal = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '20px',
  },
  box: {
    background: '#fff',
    borderRadius: '16px',
    padding: '32px',
    width: '100%',
    maxWidth: '520px',
    boxShadow: '0 20px 60px rgba(0,0,0,.2)',
    maxHeight: '90vh',
    overflowY: 'auto',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '24px',
  },
  title:    { fontSize: '20px', fontWeight: '800', color: '#1a1a1a', margin: 0 },
  closeBtn: { background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: '#9ca3af', padding: '4px' },
  form:   { display: 'flex', flexDirection: 'column', gap: '16px' },
  row:    {},
  row2:   { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' },
  col:    {},
  label:  { display: 'block', fontSize: '13px', fontWeight: '700', color: '#374151', marginBottom: '6px' },
  input:  {
    border: '1.5px solid #e5e7eb',
    borderRadius: '8px',
    padding: '10px 14px',
    fontSize: '14px',
    fontFamily: 'inherit',
    outline: 'none',
    background: '#fff',
    width: '100%',
    boxSizing: 'border-box',
  },
  hint:   { fontSize: '12px', color: '#9ca3af', marginTop: '5px' },
  error:  {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    padding: '10px 14px',
    fontSize: '13px',
    color: '#dc2626',
  },
  footer:    { display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '4px' },
  btnCancel: {
    background: 'transparent',
    border: '1.5px solid #e5e7eb',
    borderRadius: '8px',
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: '700',
    fontFamily: 'inherit',
    cursor: 'pointer',
    color: '#6b7280',
  },
  btnSave: {
    background: '#a91d7a',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: '700',
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
}
