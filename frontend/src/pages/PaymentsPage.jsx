// =============================================================================
// KARI.Самозанятые — Страница «Выплаты» (кабинет директора региона)
// =============================================================================
//
// Два таба:
//  💸 Выплаты    — список индивидуальных выплат
//  📂 Реестры    — массовые выплаты по Excel (до 1000 строк, Совкомбанк)

import { useState, useEffect, useRef, useCallback } from 'react'
import { paymentsAPI } from '../api/client.js'
import { DEMO_PAYMENTS, DEMO_REGISTRIES } from '../api/demo.js'

// Статусы выплат
const PAYMENT_STATUS = {
  pending:    { label: 'Ожидает',      color: '#92400e', bg: '#fef3c7' },
  processing: { label: 'В обработке',  color: '#1d4ed8', bg: '#eff6ff' },
  paid:       { label: 'Выплачено',    color: '#065f46', bg: '#d1fae5' },
  failed:     { label: 'Ошибка',       color: '#991b1b', bg: '#fee2e2' },
  cancelled:  { label: 'Отменено',     color: '#374151', bg: '#f3f4f6' },
}

// Статусы реестров
const REGISTRY_STATUS = {
  pending:    { label: 'На проверке',  color: '#92400e', bg: '#fef3c7' },
  approved:   { label: 'Одобрен',      color: '#065f46', bg: '#d1fae5' },
  processing: { label: 'Выплачивается',color: '#1d4ed8', bg: '#eff6ff' },
  completed:  { label: 'Завершён',     color: '#065f46', bg: '#d1fae5' },
  rejected:   { label: 'Отклонён',     color: '#991b1b', bg: '#fee2e2' },
}

export default function PaymentsPage() {
  const [tab, setTab] = useState('payments')

  return (
    <div>

      {/* Заголовок */}
      <div style={styles.pageHeader}>
        <div>
          <h1 style={styles.pageTitle}>Выплаты</h1>
          <p style={styles.pageSubtitle}>Управление выплатами самозанятым через Совкомбанк</p>
        </div>
      </div>

      {/* Переключатель табов */}
      <div style={styles.tabBar}>
        <button
          style={{ ...styles.tab, ...(tab === 'payments' ? styles.tabActive : {}) }}
          onClick={() => setTab('payments')}
        >
          💸 Выплаты
        </button>
        <button
          style={{ ...styles.tab, ...(tab === 'registries' ? styles.tabActive : {}) }}
          onClick={() => setTab('registries')}
        >
          📂 Реестры (Excel)
        </button>
      </div>

      {/* Контент таба */}
      {tab === 'payments'   && <PaymentsTab />}
      {tab === 'registries' && <RegistriesTab />}

    </div>
  )
}

// =============================================================================
// Таб: список выплат
// =============================================================================
function PaymentsTab() {
  const [payments, setPayments] = useState([])
  const [total,    setTotal]    = useState(0)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [page,     setPage]     = useState(1)

  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await paymentsAPI.getList({
        skip:  (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      const items = data.items ?? data
      const arr   = Array.isArray(items) ? items : []
      if (arr.length === 0) throw new Error('empty')
      setPayments(arr)
      setTotal(data.total ?? arr.length)
    } catch {
      // Бэкенд недоступен или нет данных — показываем демо-данные
      setPayments(DEMO_PAYMENTS.items)
      setTotal(DEMO_PAYMENTS.total)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { load() }, [load])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      {error && <div style={styles.errorBox}>{error}</div>}

      <div style={styles.tableWrap}>
        {loading ? <Placeholder text="Загрузка..." /> :
         payments.length === 0 ? <Placeholder text="Выплат пока нет" /> : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>ID</th>
                <th style={styles.th}>Исполнитель</th>
                <th style={styles.th}>Задание</th>
                <th style={styles.th}>Сумма</th>
                <th style={styles.th}>Налог (6%)</th>
                <th style={styles.th}>Итого</th>
                <th style={styles.th}>Статус</th>
                <th style={styles.th}>Дата</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(p => {
                const st = PAYMENT_STATUS[p.status] || PAYMENT_STATUS.pending
                const total = p.amount + (p.tax_amount || 0)

                return (
                  <tr key={p.id} style={styles.tr}>
                    <td style={{ ...styles.td, color: '#9ca3af', fontSize: '12px', fontFamily: 'monospace' }}>
                      #{p.id}
                    </td>
                    <td style={styles.td}>
                      <div style={styles.personName}>{p.executor_name || '—'}</div>
                      {p.executor_inn && (
                        <div style={styles.personInn}>ИНН: {p.executor_inn}</div>
                      )}
                    </td>
                    <td style={styles.td}>
                      <span style={styles.secondary}>{p.task_title || '—'}</span>
                    </td>
                    <td style={styles.td}>
                      <span style={styles.amount}>{formatMoney(p.amount)}</span>
                    </td>
                    <td style={styles.td}>
                      <span style={styles.tax}>
                        {p.tax_amount != null ? formatMoney(p.tax_amount) : '—'}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <span style={styles.totalAmount}>{formatMoney(total)}</span>
                    </td>
                    <td style={styles.td}>
                      <span style={{ ...styles.badge, color: st.color, background: st.bg }}>
                        {st.label}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <span style={styles.date}>{formatDate(p.created_at)}</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Пагинация */}
      {totalPages > 1 && <Pagination page={page} total={totalPages} onChange={setPage} />}
    </div>
  )
}

// =============================================================================
// Таб: реестры (массовые выплаты)
// =============================================================================
function RegistriesTab() {
  const [registries, setRegistries] = useState([])
  const [total,      setTotal]      = useState(0)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [uploading,  setUploading]  = useState(false)
  const [approvingId, setApprovingId] = useState(null)
  const [page,       setPage]       = useState(1)
  const fileInputRef = useRef(null)

  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await paymentsAPI.getRegistries({
        skip:  (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      const items = data.items ?? data
      const arr   = Array.isArray(items) ? items : []
      if (arr.length === 0) throw new Error('empty')
      setRegistries(arr)
      setTotal(data.total ?? arr.length)
    } catch {
      // Бэкенд недоступен или нет данных — показываем демо-данные
      setRegistries(DEMO_REGISTRIES.items)
      setTotal(DEMO_REGISTRIES.total)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { load() }, [load])

  // Загрузка Excel-файла
  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError('')
    try {
      await paymentsAPI.uploadRegistry(file)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка загрузки файла. Проверьте формат (xlsx, до 1000 строк).')
    } finally {
      setUploading(false)
      // Сбрасываем выбор файла чтобы можно было загрузить тот же файл повторно
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // Одобрить реестр и запустить выплаты
  const handleApprove = async (id) => {
    setApprovingId(id)
    setError('')
    try {
      await paymentsAPI.approveRegistry(id)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка одобрения реестра')
    } finally {
      setApprovingId(null)
    }
  }

  // Скачать реестр в Excel
  const handleExport = async (id, fileName) => {
    setError('')
    try {
      const { data } = await paymentsAPI.exportRegistry(id)
      // Создаём временную ссылку для скачивания blob
      const url = URL.createObjectURL(new Blob([data]))
      const a   = document.createElement('a')
      a.href     = url
      a.download = `registry_${id}_export.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Не удалось скачать файл')
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>

      {/* Панель загрузки реестра */}
      <div style={styles.uploadPanel}>
        <div style={styles.uploadText}>
          <div style={styles.uploadTitle}>📤 Загрузить Excel-реестр выплат</div>
          <div style={styles.uploadHint}>
            Формат: .xlsx или .xls · До 1000 строк · Столбцы: ИНН, ФИО, Сумма, Задание
          </div>
        </div>
        {/* Скрытый input type="file" */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <button
          style={uploading ? { ...styles.btnUpload, opacity: .7, cursor: 'not-allowed' } : styles.btnUpload}
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? '⏳ Загружаем...' : '📂 Выбрать файл'}
        </button>
      </div>

      {error && <div style={styles.errorBox}>{error}</div>}

      {/* Таблица реестров */}
      <div style={styles.tableWrap}>
        {loading ? <Placeholder text="Загрузка..." /> :
         registries.length === 0 ? <Placeholder text="Реестров пока нет. Загрузите первый файл выше." /> : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>ID</th>
                <th style={styles.th}>Файл</th>
                <th style={styles.th}>Строк</th>
                <th style={styles.th}>Сумма всего</th>
                <th style={styles.th}>Статус</th>
                <th style={styles.th}>Загружен</th>
                <th style={styles.th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {registries.map(r => {
                const st   = REGISTRY_STATUS[r.status] || REGISTRY_STATUS.pending
                const busy = approvingId === r.id

                return (
                  <tr key={r.id} style={styles.tr}>

                    <td style={{ ...styles.td, color: '#9ca3af', fontSize: '12px', fontFamily: 'monospace' }}>
                      #{r.id}
                    </td>

                    <td style={styles.td}>
                      <div style={styles.fileName}>
                        📄 {r.file_name || `Реестр #${r.id}`}
                      </div>
                    </td>

                    <td style={styles.td}>
                      <span style={styles.secondary}>
                        {r.items_count != null ? `${r.items_count} строк` : '—'}
                      </span>
                    </td>

                    <td style={styles.td}>
                      <span style={styles.amount}>
                        {r.total_amount != null ? formatMoney(r.total_amount) : '—'}
                      </span>
                    </td>

                    <td style={styles.td}>
                      <span style={{ ...styles.badge, color: st.color, background: st.bg }}>
                        {st.label}
                      </span>
                    </td>

                    <td style={styles.td}>
                      <span style={styles.date}>{formatDate(r.created_at)}</span>
                    </td>

                    <td style={styles.td}>
                      <div style={styles.actionsCell}>
                        {/* Одобрить — только для реестров в статусе "на проверке" */}
                        {r.status === 'pending' && (
                          <button
                            style={{ ...styles.btnAct, ...styles.btnApprove }}
                            onClick={() => handleApprove(r.id)}
                            disabled={busy}
                          >
                            {busy ? '...' : '✓ Одобрить'}
                          </button>
                        )}
                        {/* Скачать Excel */}
                        <button
                          style={{ ...styles.btnAct, ...styles.btnExport }}
                          onClick={() => handleExport(r.id, r.file_name)}
                        >
                          ⬇ Excel
                        </button>
                      </div>
                    </td>

                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && <Pagination page={page} total={totalPages} onChange={setPage} />}

    </div>
  )
}

// =============================================================================
// Вспомогательные компоненты
// =============================================================================
function Placeholder({ text }) {
  return <div style={styles.placeholder}>{text}</div>
}

function Pagination({ page, total, onChange }) {
  return (
    <div style={styles.pagination}>
      <button
        style={styles.pageBtn}
        onClick={() => onChange(p => Math.max(1, p - 1))}
        disabled={page === 1}
      >
        ← Назад
      </button>
      <span style={styles.pageInfo}>Страница {page} из {total}</span>
      <button
        style={styles.pageBtn}
        onClick={() => onChange(p => Math.min(total, p + 1))}
        disabled={page === total}
      >
        Вперёд →
      </button>
    </div>
  )
}

// Форматирование
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

// ===== Стили =====
const styles = {
  pageHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: '16px',
    gap: '16px',
  },
  pageTitle:    { fontSize: '26px', fontWeight: '800', color: '#1a1a1a', margin: 0 },
  pageSubtitle: { fontSize: '14px', color: '#6b7280', marginTop: '4px', marginBottom: 0 },
  tabBar: {
    display: 'flex',
    gap: '0',
    marginBottom: '24px',
    borderBottom: '2px solid #e5e7eb',
  },
  tab: {
    background: 'none',
    border: 'none',
    padding: '10px 24px',
    fontSize: '14px',
    fontWeight: '700',
    fontFamily: 'inherit',
    cursor: 'pointer',
    color: '#6b7280',
    borderBottom: '3px solid transparent',
    marginBottom: '-2px',
    transition: 'color .15s',
  },
  tabActive: {
    color: '#a91d7a',
    borderBottomColor: '#a91d7a',
  },
  uploadPanel: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '12px',
    padding: '20px 24px',
    marginBottom: '20px',
    gap: '16px',
    flexWrap: 'wrap',
  },
  uploadText:  {},
  uploadTitle: { fontSize: '15px', fontWeight: '700', color: '#1a1a1a', marginBottom: '4px' },
  uploadHint:  { fontSize: '13px', color: '#6b7280' },
  btnUpload: {
    background: '#a91d7a',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 20px',
    fontSize: '13px',
    fontWeight: '700',
    fontFamily: 'inherit',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
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
    lineHeight: '1.6',
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
  tr:    { borderBottom: '1px solid #f5f5f5' },
  td:    { padding: '13px 16px', verticalAlign: 'middle' },
  personName: { fontSize: '14px', fontWeight: '600', color: '#1a1a1a' },
  personInn:  { fontSize: '11px', color: '#9ca3af', marginTop: '2px', fontFamily: 'monospace' },
  secondary:  { fontSize: '13px', color: '#374151' },
  amount:     { fontSize: '13px', fontWeight: '700', color: '#1a1a1a' },
  totalAmount:{ fontSize: '13px', fontWeight: '800', color: '#a91d7a' },
  tax:        { fontSize: '13px', color: '#6b7280' },
  badge:      { display: 'inline-block', padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '700' },
  date:       { fontSize: '12px', color: '#6b7280' },
  fileName:   { fontSize: '13px', fontWeight: '600', color: '#374151' },
  actionsCell:{ display: 'flex', gap: '6px', flexWrap: 'wrap' },
  btnAct:    { border: 'none', borderRadius: '6px', padding: '5px 10px', fontSize: '12px', fontWeight: '700', fontFamily: 'inherit', cursor: 'pointer' },
  btnApprove:{ background: '#d1fae5', color: '#065f46' },
  btnExport: { background: '#eff6ff', color: '#1d4ed8' },
  pagination:{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', marginTop: '20px' },
  pageBtn:   { background: '#fff', border: '1px solid #e5e7eb', borderRadius: '6px', padding: '7px 16px', fontSize: '13px', fontWeight: '600', fontFamily: 'inherit', cursor: 'pointer', color: '#374151' },
  pageInfo:  { fontSize: '13px', color: '#6b7280' },
}
