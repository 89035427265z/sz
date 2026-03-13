// =============================================================================
// KARI.Самозанятые — Страница «ФНС / Чеки» (кабинет директора региона)
// =============================================================================
//
// Функции:
//  - Список чеков ФНС с их статусами
//  - Запуск проверки всех чеков
//  - Запуск полной проверки всех исполнителей в ФНС
//  - Аннулирование чека с указанием причины

import { useState, useEffect, useCallback } from 'react'
import { fnsAPI, paymentsAPI } from '../api/client.js'
import { DEMO_RECEIPTS } from '../api/demo.js'

// Статусы чеков ФНС
const RECEIPT_STATUS = {
  pending:    { label: 'Ожидает',      color: '#92400e', bg: '#fef3c7' },
  issued:     { label: 'Сформирован',  color: '#065f46', bg: '#d1fae5' },
  cancelled:  { label: 'Аннулирован',  color: '#991b1b', bg: '#fee2e2' },
  failed:     { label: 'Ошибка',       color: '#991b1b', bg: '#fee2e2' },
  checking:   { label: 'Проверяется',  color: '#1d4ed8', bg: '#eff6ff' },
}

export default function FnsPage() {
  const [receipts,    setReceipts]    = useState([])
  const [total,       setTotal]       = useState(0)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState('')
  const [success,     setSuccess]     = useState('')
  const [page,        setPage]        = useState(1)
  const [checkingAll, setCheckingAll] = useState(false)
  const [cancelModal, setCancelModal] = useState(null) // объект чека для аннулирования

  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await paymentsAPI.getReceipts({
        skip:  (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      const items = data.items ?? data
      const arr   = Array.isArray(items) ? items : []
      if (arr.length === 0) throw new Error('empty')
      setReceipts(arr)
      setTotal(data.total ?? arr.length)
    } catch {
      // Бэкенд недоступен или нет данных — показываем демо-данные
      setReceipts(DEMO_RECEIPTS.items)
      setTotal(DEMO_RECEIPTS.total)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { load() }, [load])

  // Проверить все чеки в ФНС
  const handleCheckReceipts = async () => {
    setCheckingAll(true)
    setError('')
    setSuccess('')
    try {
      await fnsAPI.checkAllReceipts()
      setSuccess('✅ Проверка чеков запущена. Данные обновятся через несколько минут.')
      await load()
    } catch {
      setError('Не удалось запустить проверку чеков')
    } finally {
      setCheckingAll(false)
    }
  }

  // Проверить всех исполнителей в ФНС
  const handleCheckUsers = async () => {
    setCheckingAll(true)
    setError('')
    setSuccess('')
    try {
      await fnsAPI.checkAllUsers()
      setSuccess('✅ Проверка самозанятых в ФНС запущена. Данные обновятся через несколько минут.')
      await load()
    } catch {
      setError('Не удалось запустить проверку ФНС')
    } finally {
      setCheckingAll(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>

      {/* Заголовок + кнопки проверки */}
      <div style={styles.pageHeader}>
        <div>
          <h1 style={styles.pageTitle}>ФНС / Чеки</h1>
          <p style={styles.pageSubtitle}>
            Интеграция с API «Мой налог». Ежедневная проверка в 07:00 МСК.
          </p>
        </div>
        <div style={styles.headerActions}>
          <button
            style={checkingAll ? { ...styles.btnSecondary, opacity: .7 } : styles.btnSecondary}
            onClick={handleCheckUsers}
            disabled={checkingAll}
          >
            👥 Проверить самозанятых
          </button>
          <button
            style={checkingAll ? { ...styles.btnPrimary, opacity: .7 } : styles.btnPrimary}
            onClick={handleCheckReceipts}
            disabled={checkingAll}
          >
            {checkingAll ? '⏳ Проверяем...' : '🔍 Проверить все чеки'}
          </button>
        </div>
      </div>

      {/* Уведомления */}
      {error   && <div style={styles.errorBox}>{error}</div>}
      {success && <div style={styles.successBox}>{success}</div>}

      {/* Информационная плашка */}
      <div style={styles.infoBox}>
        <span style={styles.infoIcon}>ℹ️</span>
        <div>
          <strong>Автоматический контроль аннулирования.</strong>{' '}
          Система ежедневно проверяет статус всех чеков в ФНС «Мой налог».
          Аннулированные чеки помечаются красным — исполнитель должен переоформить.
        </div>
      </div>

      {/* ===== Таблица чеков ===== */}
      <div style={styles.tableWrap}>
        {loading ? (
          <div style={styles.placeholder}>Загрузка...</div>
        ) : receipts.length === 0 ? (
          <div style={styles.placeholder}>
            Чеков пока нет. Они появятся после первых выплат самозанятым.
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>ID чека ФНС</th>
                <th style={styles.th}>Исполнитель</th>
                <th style={styles.th}>Сумма</th>
                <th style={styles.th}>Статус</th>
                <th style={styles.th}>Дата проверки</th>
                <th style={styles.th}>Дата создания</th>
                <th style={styles.th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map(r => {
                const st = RECEIPT_STATUS[r.status] || RECEIPT_STATUS.pending

                return (
                  <tr key={r.id} style={styles.tr}>

                    <td style={styles.td}>
                      <span style={styles.receiptId}>
                        {r.fns_receipt_id || <span style={styles.muted}>—</span>}
                      </span>
                    </td>

                    <td style={styles.td}>
                      <div style={styles.personName}>{r.executor_name || '—'}</div>
                      {r.executor_inn && (
                        <div style={styles.personInn}>ИНН: {r.executor_inn}</div>
                      )}
                    </td>

                    <td style={styles.td}>
                      <span style={styles.amount}>
                        {r.amount != null ? formatMoney(r.amount) : '—'}
                      </span>
                    </td>

                    <td style={styles.td}>
                      <span style={{ ...styles.badge, color: st.color, background: st.bg }}>
                        {st.label}
                      </span>
                    </td>

                    <td style={styles.td}>
                      <span style={styles.date}>
                        {r.last_checked_at ? formatDate(r.last_checked_at) : '—'}
                      </span>
                    </td>

                    <td style={styles.td}>
                      <span style={styles.date}>{formatDate(r.created_at)}</span>
                    </td>

                    <td style={styles.td}>
                      {/* Аннулировать — только для активных чеков */}
                      {r.status === 'issued' && (
                        <button
                          style={{ ...styles.btnAct, ...styles.btnCancel }}
                          onClick={() => setCancelModal(r)}
                        >
                          Аннулировать
                        </button>
                      )}
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

      {/* Модальное окно аннулирования */}
      {cancelModal && (
        <CancelReceiptModal
          receipt={cancelModal}
          onClose={() => setCancelModal(null)}
          onCancelled={() => { setCancelModal(null); load() }}
        />
      )}

    </div>
  )
}

// =============================================================================
// Модальное окно аннулирования чека
// =============================================================================
function CancelReceiptModal({ receipt, onClose, onCancelled }) {
  const [reason,  setReason]  = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!reason.trim()) { setError('Укажите причину аннулирования'); return }
    setLoading(true)
    setError('')
    try {
      await fnsAPI.cancelReceipt(receipt.id, reason.trim())
      onCancelled()
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка аннулирования чека')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={modal.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={modal.box}>
        <div style={modal.header}>
          <h2 style={modal.title}>Аннулировать чек</h2>
          <button style={modal.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div style={modal.receiptInfo}>
          <div>Исполнитель: <strong>{receipt.executor_name || '—'}</strong></div>
          <div>Сумма: <strong>{receipt.amount != null ? formatMoney(receipt.amount) : '—'}</strong></div>
          {receipt.fns_receipt_id && (
            <div style={{ marginTop: '4px', fontSize: '12px', color: '#6b7280' }}>
              Чек ФНС: {receipt.fns_receipt_id}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} style={modal.form}>
          <label style={modal.label}>Причина аннулирования *</label>
          <textarea
            style={modal.textarea}
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Укажите причину: ошибочная сумма, дублирование, и т.д."
            rows={3}
            required
          />

          {error && <div style={modal.error}>{error}</div>}

          <div style={modal.footer}>
            <button type="button" style={modal.btnCancel} onClick={onClose}>
              Отмена
            </button>
            <button
              type="submit"
              style={loading ? { ...modal.btnDanger, opacity: .6 } : modal.btnDanger}
              disabled={loading}
            >
              {loading ? 'Аннулируем...' : 'Аннулировать чек'}
            </button>
          </div>
        </form>
      </div>
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
    marginBottom: '20px',
    gap: '16px',
    flexWrap: 'wrap',
  },
  pageTitle:    { fontSize: '26px', fontWeight: '800', color: '#1a1a1a', margin: 0 },
  pageSubtitle: { fontSize: '14px', color: '#6b7280', marginTop: '4px', marginBottom: 0 },
  headerActions: { display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-start' },
  btnPrimary: {
    background: '#a91d7a', color: '#fff', border: 'none', borderRadius: '8px',
    padding: '10px 18px', fontSize: '13px', fontWeight: '700', fontFamily: 'inherit',
    cursor: 'pointer', whiteSpace: 'nowrap',
  },
  btnSecondary: {
    background: '#fff', color: '#374151', border: '1.5px solid #e5e7eb', borderRadius: '8px',
    padding: '10px 18px', fontSize: '13px', fontWeight: '700', fontFamily: 'inherit',
    cursor: 'pointer', whiteSpace: 'nowrap',
  },
  errorBox: {
    background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px',
    padding: '12px 16px', fontSize: '13px', color: '#dc2626', marginBottom: '16px',
  },
  successBox: {
    background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px',
    padding: '12px 16px', fontSize: '13px', color: '#065f46', marginBottom: '16px',
  },
  infoBox: {
    display: 'flex', gap: '12px', alignItems: 'flex-start',
    background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '10px',
    padding: '14px 18px', marginBottom: '20px', fontSize: '13px', color: '#1e40af',
    lineHeight: '1.5',
  },
  infoIcon: { fontSize: '16px', flexShrink: 0, marginTop: '1px' },
  tableWrap: {
    background: '#fff', borderRadius: '12px', border: '1px solid #e5e7eb', overflow: 'hidden',
  },
  placeholder: {
    padding: '56px', textAlign: 'center', color: '#9ca3af', fontSize: '14px', lineHeight: '1.6',
  },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: {
    padding: '12px 16px', textAlign: 'left', fontSize: '11px', fontWeight: '700',
    color: '#6b7280', textTransform: 'uppercase', letterSpacing: '.05em',
    background: '#f9fafb', borderBottom: '1px solid #e5e7eb',
  },
  tr:    { borderBottom: '1px solid #f5f5f5' },
  td:    { padding: '13px 16px', verticalAlign: 'middle' },
  receiptId: { fontSize: '12px', fontFamily: 'monospace', color: '#374151' },
  personName: { fontSize: '14px', fontWeight: '600', color: '#1a1a1a' },
  personInn:  { fontSize: '11px', color: '#9ca3af', marginTop: '2px', fontFamily: 'monospace' },
  amount:     { fontSize: '13px', fontWeight: '700', color: '#1a1a1a' },
  badge:      { display: 'inline-block', padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '700' },
  date:       { fontSize: '12px', color: '#6b7280' },
  muted:      { color: '#9ca3af' },
  btnAct:    { border: 'none', borderRadius: '6px', padding: '5px 12px', fontSize: '12px', fontWeight: '700', fontFamily: 'inherit', cursor: 'pointer' },
  btnCancel: { background: '#fee2e2', color: '#dc2626' },
  pagination:{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', marginTop: '20px' },
  pageBtn:   { background: '#fff', border: '1px solid #e5e7eb', borderRadius: '6px', padding: '7px 16px', fontSize: '13px', fontWeight: '600', fontFamily: 'inherit', cursor: 'pointer', color: '#374151' },
  pageInfo:  { fontSize: '13px', color: '#6b7280' },
}

const modal = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px',
  },
  box: {
    background: '#fff', borderRadius: '16px', padding: '32px', width: '100%', maxWidth: '460px',
    boxShadow: '0 20px 60px rgba(0,0,0,.2)',
  },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' },
  title:    { fontSize: '20px', fontWeight: '800', color: '#1a1a1a', margin: 0 },
  closeBtn: { background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: '#9ca3af' },
  receiptInfo: {
    background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px',
    padding: '12px 16px', marginBottom: '20px', fontSize: '14px', color: '#374151',
    lineHeight: '1.7',
  },
  form:     { display: 'flex', flexDirection: 'column', gap: '12px' },
  label:    { fontSize: '13px', fontWeight: '700', color: '#374151' },
  textarea: {
    border: '1.5px solid #e5e7eb', borderRadius: '8px', padding: '10px 14px',
    fontSize: '14px', fontFamily: 'inherit', outline: 'none', resize: 'vertical',
    width: '100%', boxSizing: 'border-box',
  },
  error:    {
    background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px',
    padding: '10px 14px', fontSize: '13px', color: '#dc2626',
  },
  footer:    { display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '4px' },
  btnCancel: {
    background: 'transparent', border: '1.5px solid #e5e7eb', borderRadius: '8px',
    padding: '10px 20px', fontSize: '14px', fontWeight: '700', fontFamily: 'inherit',
    cursor: 'pointer', color: '#6b7280',
  },
  btnDanger: {
    background: '#dc2626', color: '#fff', border: 'none', borderRadius: '8px',
    padding: '10px 20px', fontSize: '14px', fontWeight: '700', fontFamily: 'inherit', cursor: 'pointer',
  },
}
