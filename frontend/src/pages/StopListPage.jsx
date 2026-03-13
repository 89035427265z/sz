// =============================================================================
// KARI.Самозанятые — Страница «Стоп-лист» (кабинет HRD / директора региона)
// =============================================================================
//
// Управление стоп-листом исполнителей.
// Доступ: директор региона + HRD (бухгалтерия).
//
// Функции:
//  - Таблица заблокированных ИНН с причинами и сроками
//  - Добавление вручную (один ИНН)
//  - Массовый импорт из Excel (бывшие сотрудники)
//  - Снятие блокировки досрочно
//  - Поиск по ИНН и ФИО
//
// Правовое основание: 422-ФЗ ст.6 п.2 пп.8 (бывший работодатель < 2 лет)
// =============================================================================

import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api/client.js'

// ─── Цвета причин ─────────────────────────────────────────────────────────
const REASON_META = {
  former_employee: {
    label: 'Бывший сотрудник',
    color: '#92400e',
    bg:    '#fef3c7',
    icon:  '👤',
    desc:  'Работал в KARI менее 2 лет назад. По 422-ФЗ нельзя нанимать как самозанятого.',
  },
  fns_fine: {
    label: 'Штраф ФНС',
    color: '#991b1b',
    bg:    '#fee2e2',
    icon:  '⚠️',
    desc:  'По ИНН зафиксированы нарушения в ФНС. Выдача заданий заблокирована.',
  },
  manual: {
    label: 'Ручная блокировка',
    color: '#1d4ed8',
    bg:    '#eff6ff',
    icon:  '🔒',
    desc:  'Добавлен вручную HR-службой. Бессрочно до снятия.',
  },
  // v2: добавлен автоматически при срабатывании всех 3 критериев ФНС (fiscal_risk_tasks.py)
  fiscal_risk: {
    label: 'Фискальный риск',
    color: '#7c2d12',
    bg:    '#fff7ed',
    icon:  '🏛️',
    desc:  'Все 3 критерия ФНС сработали — риск переквалификации в трудовые отношения. Добавлено автоматически.',
  },
}

// ─── Демо-данные ──────────────────────────────────────────────────────────
const DEMO_ENTRIES = [
  {
    id: 'sl-001',
    inn: '381534210012',
    full_name: 'Захаров Артём Николаевич',
    reason: 'former_employee',
    reason_label: 'Бывший сотрудник',
    reason_details: 'Приказ №112-У от 15.01.2025. ТЦ «Мегас», продавец-консультант.',
    employment_end_date: '2025-01-15',
    blocked_until: '2027-01-15',
    created_at: '2026-01-18T09:00:00Z',
    is_active: true,
    is_expired: false,
  },
  {
    id: 'sl-002',
    inn: '381534210034',
    full_name: 'Морозова Светлана Игоревна',
    reason: 'former_employee',
    reason_label: 'Бывший сотрудник',
    reason_details: 'Приказ №87-У от 20.09.2024. ТЦ «Карамель», кладовщик.',
    employment_end_date: '2024-09-20',
    blocked_until: '2026-09-20',
    created_at: '2025-09-21T11:30:00Z',
    is_active: true,
    is_expired: false,
  },
  {
    id: 'sl-003',
    inn: '381534210056',
    full_name: 'Волков Дмитрий Юрьевич',
    reason: 'fns_fine',
    reason_label: 'Штраф ФНС',
    reason_details: 'Уведомление ФНС от 12.02.2026 — аннулированный чек на сумму 45 000 руб.',
    employment_end_date: null,
    blocked_until: null,
    created_at: '2026-02-13T14:00:00Z',
    is_active: true,
    is_expired: false,
  },
  {
    id: 'sl-004',
    inn: '381534210078',
    full_name: 'Степанова Ирина Петровна',
    reason: 'manual',
    reason_label: 'Ручная блокировка',
    reason_details: 'Конфликтная ситуация с директором магазина. Решение директора региона.',
    employment_end_date: null,
    blocked_until: null,
    created_at: '2026-03-01T10:00:00Z',
    is_active: true,
    is_expired: false,
  },
]

// ─── Вспомогательные ────────────────────────────────────────────────────
const fmtDate = (isoStr) => {
  if (!isoStr) return '—'
  try {
    const d = new Date(isoStr)
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
  } catch { return isoStr }
}

const daysLeft = (isoStr) => {
  if (!isoStr) return null
  const diff = new Date(isoStr) - new Date()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}


// =============================================================================
// ГЛАВНЫЙ КОМПОНЕНТ
// =============================================================================
export default function StopListPage() {
  const [entries,     setEntries]   = useState(DEMO_ENTRIES)
  const [loading,     setLoading]   = useState(false)
  const [error,       setError]     = useState('')
  const [success,     setSuccess]   = useState('')
  const [search,      setSearch]    = useState('')
  const [reasonFilter,setRFilter]   = useState('all')
  const [addModal,    setAddModal]  = useState(false)
  const [deactModal,  setDeactModal]= useState(null)   // объект записи для деактивации
  const [importMsg,   setImportMsg] = useState('')

  // Форма добавления
  const [form, setForm] = useState({
    inn: '', full_name: '', reason: 'former_employee',
    employment_end_date: '', reason_details: '',
  })
  const fileInputRef = useRef(null)

  // ── Загрузка данных ──────────────────────────────────────────────────
  const loadEntries = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get('/api/v1/stop-list/', {
        params: { active_only: true, size: 200 },
      })
      setEntries(data.items || DEMO_ENTRIES)
    } catch {
      // Используем демо-данные если API недоступен
      setEntries(DEMO_ENTRIES)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadEntries() }, [loadEntries])

  // ── Фильтрация ───────────────────────────────────────────────────────
  const filtered = entries.filter(e => {
    const matchSearch = !search
      || e.inn?.includes(search)
      || e.full_name?.toLowerCase().includes(search.toLowerCase())
    const matchReason = reasonFilter === 'all' || e.reason === reasonFilter
    return matchSearch && matchReason
  })

  // ── Добавление вручную ───────────────────────────────────────────────
  const handleAdd = async () => {
    if (!form.inn || form.inn.length !== 12 || !/^\d+$/.test(form.inn)) {
      setError('ИНН должен содержать ровно 12 цифр')
      return
    }
    setError('')
    setLoading(true)
    try {
      await api.post('/api/v1/stop-list/', {
        inn: form.inn,
        full_name: form.full_name || undefined,
        reason: form.reason,
        reason_details: form.reason_details || undefined,
        employment_end_date: form.employment_end_date || undefined,
      })
      setSuccess(`ИНН ${form.inn} добавлен в стоп-лист`)
      setAddModal(false)
      setForm({ inn: '', full_name: '', reason: 'former_employee', employment_end_date: '', reason_details: '' })
      loadEntries()
    } catch (e) {
      // Демо: добавляем локально
      const meta = REASON_META[form.reason] || REASON_META.manual
      setEntries(prev => [{
        id: `sl-demo-${Date.now()}`,
        inn: form.inn,
        full_name: form.full_name,
        reason: form.reason,
        reason_label: meta.label,
        reason_details: form.reason_details,
        employment_end_date: form.employment_end_date || null,
        blocked_until: form.reason === 'former_employee' && form.employment_end_date
          ? new Date(new Date(form.employment_end_date).setFullYear(new Date(form.employment_end_date).getFullYear() + 2)).toISOString().split('T')[0]
          : null,
        created_at: new Date().toISOString(),
        is_active: true,
        is_expired: false,
      }, ...prev])
      setSuccess(`ИНН ${form.inn} добавлен в стоп-лист (демо)`)
      setAddModal(false)
      setForm({ inn: '', full_name: '', reason: 'former_employee', employment_end_date: '', reason_details: '' })
    } finally {
      setLoading(false)
    }
  }

  // ── Деактивация (снятие блокировки) ─────────────────────────────────
  const handleDeactivate = async (entry) => {
    setLoading(true)
    try {
      await api.put(`/api/v1/stop-list/${entry.id}/deactivate`)
      setSuccess(`Блокировка ИНН ${entry.inn} снята`)
      loadEntries()
    } catch {
      // Демо: убираем из списка
      setEntries(prev => prev.filter(e => e.id !== entry.id))
      setSuccess(`Блокировка ИНН ${entry.inn} снята (демо)`)
    } finally {
      setLoading(false)
      setDeactModal(null)
    }
  }

  // ── Импорт Excel ─────────────────────────────────────────────────────
  const handleImport = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportMsg('')
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await api.post('/api/v1/stop-list/import/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setImportMsg(`✅ Добавлено: ${data.imported}, пропущено: ${data.skipped}${data.errors?.length ? `, ошибок: ${data.errors.length}` : ''}`)
      loadEntries()
    } catch {
      setImportMsg('⚠️ Демо-режим: импорт доступен при подключённом сервере')
    }
    e.target.value = ''
  }

  // ── Автосброс сообщений ───────────────────────────────────────────────
  useEffect(() => {
    if (success || error) {
      const t = setTimeout(() => { setSuccess(''); setError('') }, 5000)
      return () => clearTimeout(t)
    }
  }, [success, error])

  // =========================================================================
  // РЕНДЕР
  // =========================================================================
  return (
    <div style={css.page}>

      {/* ── Заголовок ─────────────────────────────────────────────────── */}
      <div style={css.header}>
        <div>
          <div style={css.headerTitle}>
            <span style={{ fontSize: 28 }}>🚫</span>
            <span>Стоп-лист исполнителей</span>
          </div>
          <div style={css.headerSub}>
            Бывшие сотрудники KARI ({'< 2 лет'}) и лица со штрафами ФНС.
            Основание: <b>422-ФЗ ст. 6 п. 2 пп. 8</b>
          </div>
        </div>
        <div style={css.headerBtns}>
          {/* Импорт Excel */}
          <input
            type="file"
            accept=".xlsx,.xls"
            ref={fileInputRef}
            onChange={handleImport}
            style={{ display: 'none' }}
          />
          <button
            style={css.btnSecondary}
            onClick={() => fileInputRef.current?.click()}
          >
            📥 Импорт Excel
          </button>
          {/* Добавить вручную */}
          <button
            style={css.btnPrimary}
            onClick={() => setAddModal(true)}
          >
            + Добавить ИНН
          </button>
        </div>
      </div>

      {/* ── Шаблон Excel ─────────────────────────────────────────────── */}
      <div style={css.templateNote}>
        <span style={{ marginRight: 8 }}>📋</span>
        <span>
          Формат Excel для импорта: <b>ИНН</b> | <b>ФИО</b> | <b>Причина</b> (former_employee / fns_fine / manual) | <b>Дата увольнения</b> (ДД.ММ.ГГГГ) | <b>Комментарий</b>. Причина <b>fiscal_risk</b> добавляется автоматически системой.
        </span>
      </div>

      {/* ── Сообщения ────────────────────────────────────────────────── */}
      {(success || error || importMsg) && (
        <div style={success || importMsg.startsWith('✅') ? css.alertSuccess : css.alertError}>
          {success || importMsg || error}
        </div>
      )}

      {/* ── Фильтры ──────────────────────────────────────────────────── */}
      <div style={css.filterRow}>
        <input
          style={css.searchInput}
          placeholder="Поиск по ИНН или ФИО..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div style={css.filterTabs}>
          {[
            { key: 'all',             label: `Все (${entries.length})` },
            { key: 'former_employee', label: `👤 Бывшие сотрудники (${entries.filter(e=>e.reason==='former_employee').length})` },
            { key: 'fns_fine',        label: `⚠️ Штрафы ФНС (${entries.filter(e=>e.reason==='fns_fine').length})` },
            { key: 'manual',          label: `🔒 Ручные (${entries.filter(e=>e.reason==='manual').length})` },
            { key: 'fiscal_risk',     label: `🏛️ Фискальный риск (${entries.filter(e=>e.reason==='fiscal_risk').length})` },
          ].map(tab => (
            <button
              key={tab.key}
              style={reasonFilter === tab.key ? css.tabActive : css.tab}
              onClick={() => setRFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Таблица ───────────────────────────────────────────────────── */}
      <div style={css.tableWrap}>
        {loading ? (
          <div style={css.loadingRow}>Загрузка...</div>
        ) : filtered.length === 0 ? (
          <div style={css.emptyRow}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
            <div style={css.emptyTitle}>Стоп-лист пуст</div>
            <div style={css.emptySub}>Нет активных блокировок{search ? ' по вашему запросу' : ''}</div>
          </div>
        ) : (
          <table style={css.table}>
            <thead>
              <tr style={css.thead}>
                <th style={css.th}>ИНН / ФИО</th>
                <th style={css.th}>Причина</th>
                <th style={css.th}>Детали</th>
                <th style={css.th}>Заблокирован до</th>
                <th style={css.th}>Добавлен</th>
                <th style={css.th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(entry => {
                const meta    = REASON_META[entry.reason] || REASON_META.manual
                const days    = daysLeft(entry.blocked_until)
                const isAlmost = days !== null && days > 0 && days <= 90

                return (
                  <tr key={entry.id} style={css.tr}>
                    {/* ИНН / ФИО */}
                    <td style={css.td}>
                      <div style={css.inn}>{entry.inn}</div>
                      {entry.full_name && (
                        <div style={css.name}>{entry.full_name}</div>
                      )}
                    </td>

                    {/* Причина */}
                    <td style={css.td}>
                      <span style={{ ...css.badge, color: meta.color, background: meta.bg }}>
                        {meta.icon} {meta.label}
                      </span>
                    </td>

                    {/* Детали */}
                    <td style={{ ...css.td, maxWidth: 280 }}>
                      {entry.reason_details
                        ? <span style={css.detailText}>{entry.reason_details}</span>
                        : <span style={css.noDetail}>—</span>
                      }
                    </td>

                    {/* Заблокирован до */}
                    <td style={css.td}>
                      {entry.blocked_until ? (
                        <div>
                          <div style={css.dateVal}>{fmtDate(entry.blocked_until)}</div>
                          {days !== null && days > 0 && (
                            <div style={{ ...css.daysLeft, color: isAlmost ? '#d97706' : '#666' }}>
                              {isAlmost ? '⚠ ' : ''}{days} дней осталось
                            </div>
                          )}
                          {days !== null && days <= 0 && (
                            <div style={{ ...css.daysLeft, color: '#16a34a' }}>
                              ✓ Срок истёк (ожидает снятия)
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={css.forever}>∞ Бессрочно</span>
                      )}
                    </td>

                    {/* Добавлен */}
                    <td style={css.td}>
                      <div style={css.dateVal}>{fmtDate(entry.created_at)}</div>
                    </td>

                    {/* Действия */}
                    <td style={css.td}>
                      <button
                        style={css.btnDeact}
                        onClick={() => setDeactModal(entry)}
                        title="Снять блокировку досрочно"
                      >
                        🔓 Снять
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Подсказка ─────────────────────────────────────────────────── */}
      <div style={css.legalNote}>
        <b>⚖️ Правовое основание:</b> Федеральный закон № 422-ФЗ от 27.11.2018,
        статья 6, пункт 2, подпункт 8. Доходы от бывшего работодателя (менее 2 лет)
        не признаются объектом налогообложения НПД. При нарушении — KARI обязан
        уплатить НДФЛ 13% + страховые взносы 30%+ за исполнителя.
      </div>


      {/* ================================================================ */}
      {/* МОДАЛЬНОЕ ОКНО: Добавить ИНН                                     */}
      {/* ================================================================ */}
      {addModal && (
        <div style={css.overlay} onClick={() => setAddModal(false)}>
          <div style={css.modal} onClick={e => e.stopPropagation()}>
            <div style={css.modalHeader}>
              <span style={css.modalTitle}>+ Добавить ИНН в стоп-лист</span>
              <button style={css.modalClose} onClick={() => setAddModal(false)}>✕</button>
            </div>

            {/* ИНН */}
            <label style={css.label}>ИНН (12 цифр) *</label>
            <input
              style={css.input}
              placeholder="381234567890"
              maxLength={12}
              value={form.inn}
              onChange={e => setForm(f => ({ ...f, inn: e.target.value.replace(/\D/g, '') }))}
            />

            {/* ФИО */}
            <label style={css.label}>ФИО (для справки)</label>
            <input
              style={css.input}
              placeholder="Иванов Иван Иванович"
              value={form.full_name}
              onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
            />

            {/* Причина */}
            <label style={css.label}>Причина блокировки *</label>
            <select
              style={css.input}
              value={form.reason}
              onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            >
              <option value="former_employee">👤 Бывший сотрудник KARI (&lt; 2 лет)</option>
              <option value="fns_fine">⚠️ Штраф ФНС по этому ИНН</option>
              <option value="manual">🔒 Ручная блокировка HR</option>
            </select>

            {/* Описание причины */}
            <div style={{ ...css.reasonDesc, background: REASON_META[form.reason]?.bg, color: REASON_META[form.reason]?.color }}>
              {REASON_META[form.reason]?.desc}
            </div>

            {/* Дата увольнения — только для former_employee */}
            {form.reason === 'former_employee' && (
              <>
                <label style={css.label}>Дата увольнения *</label>
                <input
                  type="date"
                  style={css.input}
                  value={form.employment_end_date}
                  onChange={e => setForm(f => ({ ...f, employment_end_date: e.target.value }))}
                />
                {form.employment_end_date && (
                  <div style={css.autoNote}>
                    📅 Блокировка снимется автоматически:{' '}
                    <b>{fmtDate(new Date(new Date(form.employment_end_date).setFullYear(new Date(form.employment_end_date).getFullYear() + 2)).toISOString())}</b>
                    {' '}(через 2 года, по закону 422-ФЗ)
                  </div>
                )}
              </>
            )}

            {/* Комментарий */}
            <label style={css.label}>Комментарий</label>
            <textarea
              style={{ ...css.input, height: 70, resize: 'vertical' }}
              placeholder="Номер приказа об увольнении, номер уведомления ФНС..."
              value={form.reason_details}
              onChange={e => setForm(f => ({ ...f, reason_details: e.target.value }))}
            />

            {error && <div style={css.alertError}>{error}</div>}

            <div style={css.modalFooter}>
              <button style={css.btnSecondary} onClick={() => setAddModal(false)}>Отмена</button>
              <button style={css.btnPrimary} onClick={handleAdd} disabled={loading}>
                {loading ? 'Добавление...' : '+ Добавить в стоп-лист'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* МОДАЛЬНОЕ ОКНО: Подтверждение снятия блокировки                  */}
      {/* ================================================================ */}
      {deactModal && (
        <div style={css.overlay} onClick={() => setDeactModal(null)}>
          <div style={{ ...css.modal, maxWidth: 460 }} onClick={e => e.stopPropagation()}>
            <div style={css.modalHeader}>
              <span style={css.modalTitle}>🔓 Снять блокировку?</span>
              <button style={css.modalClose} onClick={() => setDeactModal(null)}>✕</button>
            </div>

            <div style={css.deactBody}>
              <div style={css.deactInn}>{deactModal.inn}</div>
              {deactModal.full_name && (
                <div style={css.deactName}>{deactModal.full_name}</div>
              )}
              <div style={{ ...css.badge, color: REASON_META[deactModal.reason]?.color, background: REASON_META[deactModal.reason]?.bg, display: 'inline-flex', marginTop: 8 }}>
                {REASON_META[deactModal.reason]?.icon} {REASON_META[deactModal.reason]?.label}
              </div>

              {deactModal.reason === 'former_employee' && (
                <div style={css.deactWarn}>
                  ⚠️ <b>Важно:</b> если с момента увольнения прошло менее 2 лет,
                  снятие блокировки противоречит 422-ФЗ. KARI несёт налоговый риск.
                  Убедитесь, что прошло более 2 лет, или получите согласование юриста.
                </div>
              )}
            </div>

            <div style={css.modalFooter}>
              <button style={css.btnSecondary} onClick={() => setDeactModal(null)}>Отмена</button>
              <button
                style={{ ...css.btnPrimary, background: '#dc2626' }}
                onClick={() => handleDeactivate(deactModal)}
                disabled={loading}
              >
                {loading ? 'Снимаем...' : '🔓 Да, снять блокировку'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}


// =============================================================================
// СТИЛИ
// =============================================================================
const KARI  = '#A01F72'
const DARK  = '#242D4A'

const css = {
  page: {
    minHeight: '100vh',
    background: '#f4f5f8',
    padding: '28px 32px',
    fontFamily: "'Nunito', sans-serif",
    color: DARK,
  },

  // ── Заголовок ────────────────────────────────────────────────────────
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
    flexWrap: 'wrap',
    gap: 12,
  },
  headerTitle: {
    display: 'flex', alignItems: 'center',
    gap: 12,
    fontSize: 24, fontWeight: 900,
    color: DARK,
    marginBottom: 6,
  },
  headerSub: { fontSize: 13, color: '#666' },
  headerBtns: { display: 'flex', gap: 10, flexWrap: 'wrap' },

  // ── Шаблон ───────────────────────────────────────────────────────────
  templateNote: {
    background: '#eff6ff',
    border: '1px solid #bfdbfe',
    borderRadius: 8,
    padding: '8px 14px',
    fontSize: 12,
    color: '#1e40af',
    marginBottom: 14,
    display: 'flex',
    alignItems: 'center',
  },

  // ── Уведомления ──────────────────────────────────────────────────────
  alertSuccess: {
    background: '#dcfce7', color: '#166534',
    border: '1px solid #bbf7d0',
    borderRadius: 8, padding: '10px 14px',
    fontSize: 14, fontWeight: 600,
    marginBottom: 14,
  },
  alertError: {
    background: '#fee2e2', color: '#991b1b',
    border: '1px solid #fca5a5',
    borderRadius: 8, padding: '10px 14px',
    fontSize: 14, fontWeight: 600,
    marginBottom: 14,
  },

  // ── Фильтры ───────────────────────────────────────────────────────────
  filterRow: {
    display: 'flex',
    gap: 12,
    marginBottom: 16,
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  searchInput: {
    padding: '9px 14px',
    border: '1px solid #e0e0e0',
    borderRadius: 8,
    fontSize: 14,
    outline: 'none',
    width: 260,
    background: '#fff',
  },
  filterTabs: {
    display: 'flex', gap: 6, flexWrap: 'wrap',
  },
  tab: {
    padding: '7px 14px',
    border: '1px solid #e0e0e0',
    borderRadius: 20,
    background: '#fff',
    cursor: 'pointer',
    fontSize: 13,
    color: '#555',
    fontWeight: 600,
    transition: 'all 0.15s',
  },
  tabActive: {
    padding: '7px 14px',
    border: `1px solid ${KARI}`,
    borderRadius: 20,
    background: KARI,
    cursor: 'pointer',
    fontSize: 13,
    color: '#fff',
    fontWeight: 700,
  },

  // ── Таблица ───────────────────────────────────────────────────────────
  tableWrap: {
    background: '#fff',
    borderRadius: 14,
    border: '1px solid #e8eaf0',
    overflow: 'hidden',
    marginBottom: 16,
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  thead: {
    background: DARK,
  },
  th: {
    padding: '12px 16px',
    color: '#fff',
    fontWeight: 700,
    fontSize: 12,
    textAlign: 'left',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    whiteSpace: 'nowrap',
  },
  tr: {
    borderBottom: '1px solid #f0f2f6',
  },
  td: {
    padding: '12px 16px',
    fontSize: 13,
    verticalAlign: 'top',
  },

  // ── Ячейки ────────────────────────────────────────────────────────────
  inn:  { fontWeight: 800, fontSize: 14, color: DARK, fontFamily: 'monospace, sans-serif' },
  name: { fontSize: 12, color: '#666', marginTop: 2 },
  badge: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '3px 10px', borderRadius: 20,
    fontSize: 12, fontWeight: 700,
    whiteSpace: 'nowrap',
  },
  detailText: { fontSize: 12, color: '#444', lineHeight: '16px' },
  noDetail:   { fontSize: 12, color: '#bbb' },
  dateVal:    { fontWeight: 700, color: DARK, fontSize: 13 },
  daysLeft:   { fontSize: 11, marginTop: 2 },
  forever:    { fontSize: 12, color: '#666', fontStyle: 'italic' },

  // ── Пустой список ────────────────────────────────────────────────────
  loadingRow: { padding: 40, textAlign: 'center', color: '#999', fontSize: 15 },
  emptyRow: { padding: 48, textAlign: 'center' },
  emptyTitle: { fontSize: 18, fontWeight: 800, color: DARK, marginBottom: 6 },
  emptySub:   { fontSize: 14, color: '#888' },

  // ── Кнопки ───────────────────────────────────────────────────────────
  btnPrimary: {
    padding: '9px 18px',
    background: KARI,
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: 700,
    fontFamily: 'inherit',
  },
  btnSecondary: {
    padding: '9px 18px',
    background: '#fff',
    color: DARK,
    border: '1px solid #e0e0e0',
    borderRadius: 8,
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: 700,
    fontFamily: 'inherit',
  },
  btnDeact: {
    padding: '6px 12px',
    background: '#f9f9f9',
    color: '#555',
    border: '1px solid #e0e0e0',
    borderRadius: 6,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 700,
    fontFamily: 'inherit',
    whiteSpace: 'nowrap',
  },

  // ── Правовая сноска ───────────────────────────────────────────────────
  legalNote: {
    background: '#fef3c7',
    border: '1px solid #fcd34d',
    borderRadius: 8,
    padding: '10px 16px',
    fontSize: 12,
    color: '#78350f',
    lineHeight: '18px',
  },

  // ── Модальное окно ───────────────────────────────────────────────────
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
    padding: 20,
  },
  modal: {
    background: '#fff',
    borderRadius: 16,
    padding: 28,
    width: '100%',
    maxWidth: 520,
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
    maxHeight: '90vh',
    overflowY: 'auto',
  },
  modalHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: { fontSize: 18, fontWeight: 900, color: DARK },
  modalClose: {
    background: 'none', border: 'none',
    fontSize: 20, cursor: 'pointer', color: '#999',
  },
  modalFooter: {
    display: 'flex', justifyContent: 'flex-end',
    gap: 10, marginTop: 20,
  },

  // ── Форма ────────────────────────────────────────────────────────────
  label: {
    display: 'block',
    fontSize: 12, fontWeight: 700,
    color: '#555',
    marginBottom: 4, marginTop: 12,
    textTransform: 'uppercase', letterSpacing: '0.5px',
  },
  input: {
    width: '100%',
    padding: '9px 12px',
    border: '1px solid #e0e0e0',
    borderRadius: 8,
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
    background: '#fff',
  },
  reasonDesc: {
    fontSize: 12, borderRadius: 6,
    padding: '7px 10px',
    marginTop: 6, lineHeight: '17px',
  },
  autoNote: {
    fontSize: 12, color: '#1d4ed8',
    background: '#eff6ff',
    borderRadius: 6, padding: '7px 10px',
    marginTop: 6,
  },

  // ── Деактивация ───────────────────────────────────────────────────────
  deactBody: { marginBottom: 4 },
  deactInn:  { fontSize: 22, fontWeight: 900, fontFamily: 'monospace, sans-serif', color: DARK },
  deactName: { fontSize: 14, color: '#666', marginTop: 4 },
  deactWarn: {
    marginTop: 14,
    background: '#fee2e2',
    border: '1px solid #fca5a5',
    borderRadius: 8,
    padding: '10px 14px',
    fontSize: 13, color: '#991b1b', lineHeight: '18px',
  },
}
