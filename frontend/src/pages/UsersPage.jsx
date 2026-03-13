// =============================================================================
// KARI.Самозанятые — Страница «Исполнители» (кабинет директора региона)
// =============================================================================
//
// Таблица самозанятых с:
//  - Поиском по ФИО / телефону / ИНН
//  - Цветовыми метками статуса ФНС
//  - Годовым доходом (лимит 2 400 000 ₽)
//  - Кнопками Заблокировать / Разблокировать
//  - Запуском проверки ФНС для всех исполнителей

import { useState, useEffect, useCallback } from 'react'
import { usersAPI, fnsAPI } from '../api/client.js'
import { DEMO_USERS } from '../api/demo.js'

// Метки статусов ФНС
const FNS_STATUS = {
  active:       { label: 'Самозанятый',      color: '#065f46', bg: '#d1fae5' },
  inactive:     { label: 'Не самозанятый',   color: '#991b1b', bg: '#fee2e2' },
  not_checked:  { label: 'Не проверен',      color: '#374151', bg: '#f3f4f6' },
  check_failed: { label: 'Ошибка проверки',  color: '#92400e', bg: '#fef3c7' },
}

// Метки статусов пользователя
const USER_STATUS = {
  active:   { label: 'Активен',       color: '#065f46' },
  blocked:  { label: 'Заблокирован',  color: '#991b1b' },
  pending:  { label: 'Ожидает',       color: '#92400e' },
}

// Лимит дохода самозанятого (2 400 000 ₽)
const INCOME_LIMIT = 2_400_000

export default function UsersPage() {
  const [users,      setUsers]      = useState([])
  const [total,      setTotal]      = useState(0)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [search,     setSearch]     = useState('')
  const [page,       setPage]       = useState(1)
  const [checking,   setChecking]   = useState(false)   // идёт проверка ФНС
  const [blockingId, setBlockingId] = useState(null)    // ID блокируемого пользователя

  const PAGE_SIZE = 20

  // Загрузка списка исполнителей
  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await usersAPI.getExecutors({
        search: search || undefined,
        skip:   (page - 1) * PAGE_SIZE,
        limit:  PAGE_SIZE,
      })
      // Бэкенд может вернуть { items: [...], total: N } или просто массив
      const items = data.items ?? data
      const arr   = Array.isArray(items) ? items : []
      // Если БД пустая — показываем демо-данные
      if (arr.length === 0) throw new Error('empty')
      setUsers(arr)
      setTotal(data.total ?? arr.length)
    } catch {
      // Бэкенд недоступен или нет данных — показываем демо-данные
      const filtered = search
        ? DEMO_USERS.items.filter(u =>
            u.full_name.toLowerCase().includes(search.toLowerCase()) ||
            u.phone.includes(search) ||
            (u.inn || '').includes(search)
          )
        : DEMO_USERS.items
      setUsers(filtered)
      setTotal(DEMO_USERS.total)
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { load() }, [load])

  // Проверить всех в ФНС
  const handleCheckAll = async () => {
    setChecking(true)
    setError('')
    try {
      await fnsAPI.checkAllUsers()
      await load()
    } catch {
      setError('Не удалось запустить проверку ФНС')
    } finally {
      setChecking(false)
    }
  }

  // Заблокировать / разблокировать
  const handleToggleBlock = async (user) => {
    setBlockingId(user.id)
    setError('')
    try {
      if (user.status === 'blocked') {
        await usersAPI.unblock(user.id)
      } else {
        await usersAPI.block(user.id, 'Заблокирован директором региона')
      }
      await load()
    } catch {
      setError('Ошибка при смене статуса пользователя')
    } finally {
      setBlockingId(null)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>

      {/* Заголовок */}
      <div style={styles.pageHeader}>
        <div>
          <h1 style={styles.pageTitle}>Исполнители</h1>
          <p style={styles.pageSubtitle}>
            Зарегистрированных самозанятых: <strong>{loading ? '...' : total}</strong>
          </p>
        </div>
        <button
          style={checking ? { ...styles.btnPrimary, ...styles.btnDisabled } : styles.btnPrimary}
          onClick={handleCheckAll}
          disabled={checking}
        >
          {checking ? '⏳ Проверяем ФНС...' : '🔍 Проверить всех в ФНС'}
        </button>
      </div>

      {/* Поиск */}
      <div style={styles.toolbar}>
        <div style={styles.searchWrap}>
          <span style={styles.searchIcon}>🔎</span>
          <input
            type="search"
            placeholder="Поиск по имени, телефону или ИНН..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            style={styles.searchInput}
          />
        </div>
      </div>

      {/* Ошибка */}
      {error && <div style={styles.errorBox}>{error}</div>}

      {/* ===== Таблица ===== */}
      <div style={styles.tableWrap}>
        {loading ? (
          <div style={styles.placeholder}>Загрузка...</div>
        ) : users.length === 0 ? (
          <div style={styles.placeholder}>
            {search ? `По запросу «${search}» ничего не найдено` : 'Исполнители не найдены'}
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>ФИО</th>
                <th style={styles.th}>Телефон</th>
                <th style={styles.th}>ИНН</th>
                <th style={styles.th}>Статус ФНС</th>
                <th style={styles.th}>Доход (год)</th>
                <th style={styles.th}>Статус</th>
                <th style={styles.th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const fns  = FNS_STATUS[u.fns_status]  || FNS_STATUS.not_checked
                const us   = USER_STATUS[u.status]      || USER_STATUS.active
                const busy = blockingId === u.id

                // Процент использования лимита дохода
                const incomePercent = u.annual_income
                  ? Math.min(100, (u.annual_income / INCOME_LIMIT) * 100)
                  : 0
                const incomeWarn = incomePercent >= 80

                return (
                  <tr key={u.id} style={styles.tr}>

                    {/* ФИО */}
                    <td style={styles.td}>
                      <div style={styles.fullName}>{u.full_name || '—'}</div>
                    </td>

                    {/* Телефон */}
                    <td style={styles.td}>
                      <span style={styles.mono}>{u.phone}</span>
                    </td>

                    {/* ИНН */}
                    <td style={styles.td}>
                      <span style={styles.mono}>{u.inn || '—'}</span>
                    </td>

                    {/* Статус ФНС */}
                    <td style={styles.td}>
                      <span style={{ ...styles.badge, color: fns.color, background: fns.bg }}>
                        {fns.label}
                      </span>
                    </td>

                    {/* Доход с прогресс-баром */}
                    <td style={styles.td}>
                      {u.annual_income != null ? (
                        <div>
                          <div style={{
                            ...styles.incomeText,
                            color: incomeWarn ? '#dc2626' : '#1a1a1a',
                          }}>
                            {formatMoney(u.annual_income)}
                            {incomeWarn && <span style={styles.warnBadge}>⚠ {Math.round(incomePercent)}%</span>}
                          </div>
                          {/* Прогресс-бар */}
                          <div style={styles.progressBg}>
                            <div style={{
                              ...styles.progressFill,
                              width: incomePercent + '%',
                              background: incomeWarn ? '#ef4444' : '#10b981',
                            }} />
                          </div>
                        </div>
                      ) : (
                        <span style={styles.muted}>—</span>
                      )}
                    </td>

                    {/* Статус пользователя */}
                    <td style={styles.td}>
                      <span style={{ ...styles.statusText, color: us.color }}>
                        ● {us.label}
                      </span>
                    </td>

                    {/* Действия */}
                    <td style={styles.td}>
                      {u.status !== 'pending' && (
                        <button
                          style={{
                            ...styles.btnAction,
                            ...(u.status === 'blocked' ? styles.btnUnblock : styles.btnBlock),
                          }}
                          onClick={() => handleToggleBlock(u)}
                          disabled={busy}
                        >
                          {busy
                            ? '...'
                            : u.status === 'blocked'
                              ? 'Разблокировать'
                              : 'Заблокировать'}
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

    </div>
  )
}

// Форматирование суммы в рублях
function formatMoney(v) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(v)
}

// ===== Стили =====
const styles = {
  pageHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: '24px',
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
  btnDisabled: { background: '#d1d5db', cursor: 'not-allowed' },
  toolbar: { marginBottom: '16px' },
  searchWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: '#fff',
    border: '1.5px solid #e5e7eb',
    borderRadius: '8px',
    padding: '0 14px',
    width: '360px',
  },
  searchIcon: { fontSize: '14px', color: '#9ca3af' },
  searchInput: {
    border: 'none',
    outline: 'none',
    fontSize: '14px',
    fontFamily: 'inherit',
    flex: 1,
    padding: '10px 0',
    background: 'transparent',
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
  tr: {
    borderBottom: '1px solid #f5f5f5',
  },
  td: {
    padding: '14px 16px',
    verticalAlign: 'middle',
  },
  fullName: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#1a1a1a',
  },
  mono: {
    fontSize: '13px',
    fontFamily: 'monospace',
    color: '#374151',
    letterSpacing: '.02em',
  },
  badge: {
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: '700',
  },
  incomeText: {
    fontSize: '13px',
    fontWeight: '700',
    marginBottom: '4px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  warnBadge: {
    fontSize: '11px',
    fontWeight: '800',
    color: '#dc2626',
    background: '#fee2e2',
    borderRadius: '10px',
    padding: '1px 7px',
  },
  progressBg: {
    height: '4px',
    background: '#f0f0f0',
    borderRadius: '2px',
    overflow: 'hidden',
    width: '120px',
  },
  progressFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width .3s',
  },
  muted: { color: '#9ca3af', fontSize: '13px' },
  statusText: { fontSize: '12px', fontWeight: '700' },
  btnAction: {
    border: 'none',
    borderRadius: '6px',
    padding: '5px 12px',
    fontSize: '12px',
    fontWeight: '700',
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  btnBlock:   { background: '#fee2e2', color: '#dc2626' },
  btnUnblock: { background: '#d1fae5', color: '#065f46' },
  pagination: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    marginTop: '20px',
  },
  pageBtn: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '6px',
    padding: '7px 16px',
    fontSize: '13px',
    fontWeight: '600',
    fontFamily: 'inherit',
    cursor: 'pointer',
    color: '#374151',
  },
  pageInfo: { fontSize: '13px', color: '#6b7280' },
}
