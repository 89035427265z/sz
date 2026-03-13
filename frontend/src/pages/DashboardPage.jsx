// =============================================================================
// KARI.Самозанятые — Обзорная страница кабинета директора региона
// =============================================================================
//
// Структура (сверху вниз):
//   1. 🚨 Сигналы     — риски и проблемы, требующие внимания
//   2. 💰 Бюджет      — регион → подразделения (раскрываются) → магазины
//   3. 📊 Статистика  — общие цифры
//
// Примечание: сейчас используются демо-данные.
// После подключения бэкенда данные будут грузиться с /api/v1/dashboard/summary

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

// =============================================================================
// ДЕМО-ДАННЫЕ (заменить на API-запросы после запуска бэкенда)
// =============================================================================

const DEMO_ALERTS = [
  {
    id: 1,
    level: 'critical',
    title: '2 исполнителя близко к лимиту дохода',
    desc: 'Иванов И.И. — 2 180 000 ₽ (91%) · Петров А.С. — 1 980 000 ₽ (82%). При достижении 2 400 000 ₽ система заблокирует новые задания.',
    action: 'Смотреть исполнителей',
    link: '/dashboard/users',
  },
  {
    id: 2,
    level: 'critical',
    title: 'Риск перерасхода бюджета: подр. «Иркутск Запад»',
    desc: 'Использовано 87% квартального бюджета. Остаток 78 000 ₽. Основная нагрузка — ТЦ «Мегас» (95%).',
    action: 'Перейти в подразделение',
    divisionId: 2,
  },
  {
    id: 3,
    level: 'warning',
    title: '1 аннулированный чек ФНС',
    desc: 'Чек #4521 от 14.02.2026 аннулирован налоговой. Выплата заморожена до переоформления.',
    action: 'Перейти в ФНС / Чеки',
    link: '/dashboard/fns',
  },
  {
    id: 4,
    level: 'warning',
    title: 'Исполнитель утратил статус самозанятого',
    desc: 'Сидоров В.К. (ИНН 7712345678) — статус ФНС изменился на «Не самозанятый». Активных заданий: 2.',
    action: 'Смотреть исполнителей',
    link: '/dashboard/users',
  },
]

const DEMO_DIVISIONS = [
  {
    id: 1,
    name: 'Иркутск Центр',
    budget_total: 800_000,
    budget_used:  336_000,
    executors: 18,
    tasks_active: 4,
    stores: [
      { id: 101, name: 'ТЦ «Карамель»',         budget_total: 300_000, budget_used: 126_000, tasks: 2, executors: 7 },
      { id: 102, name: 'ТЦ «Модный квартал»',   budget_total: 300_000, budget_used: 130_000, tasks: 1, executors: 6 },
      { id: 103, name: 'ТЦ «Торговый квартал»', budget_total: 200_000, budget_used:  80_000, tasks: 1, executors: 5 },
    ],
  },
  {
    id: 2,
    name: 'Иркутск Запад',
    budget_total: 600_000,
    budget_used:  522_000,
    executors: 21,
    tasks_active: 8,
    risk: 'budget',
    stores: [
      { id: 201, name: 'ТЦ «Мегас»',        budget_total: 300_000, budget_used: 285_000, tasks: 4, executors: 9, risk: 'budget' },
      { id: 202, name: 'ТЦ «Сильвер Молл»', budget_total: 200_000, budget_used: 145_000, tasks: 3, executors: 8 },
      { id: 203, name: 'ТЦ «Аквамолл»',     budget_total: 100_000, budget_used:  92_000, tasks: 1, executors: 4, risk: 'budget' },
    ],
  },
  {
    id: 3,
    name: 'Иркутск Север',
    budget_total: 1_000_000,
    budget_used:    310_000,
    executors: 24,
    tasks_active: 5,
    stores: [
      { id: 301, name: 'ТЦ «СМ Сити»',   budget_total: 400_000, budget_used: 160_000, tasks: 3, executors: 10 },
      { id: 302, name: 'ТЦ «Радуга»',    budget_total: 350_000, budget_used: 100_000, tasks: 1, executors: 8  },
      { id: 303, name: 'ТЦ «Квадрат»',   budget_total: 250_000, budget_used:  50_000, tasks: 1, executors: 6  },
    ],
  },
]

const DEMO_STATS = {
  total_executors:  63,
  active_tasks:     17,
  paid_month: 1_168_000,
  pending_pay:       3,
}

// =============================================================================
// Главный компонент
// =============================================================================
export default function DashboardPage() {
  const navigate = useNavigate()
  // ID раскрытого подразделения (null = все свёрнуты)
  const [openDivision, setOpenDivision] = useState(null)

  // Итоги по региону
  const regionTotal   = DEMO_DIVISIONS.reduce((s, d) => s + d.budget_total, 0)
  const regionUsed    = DEMO_DIVISIONS.reduce((s, d) => s + d.budget_used,  0)
  const regionPercent = Math.round((regionUsed / regionTotal) * 100)

  const criticalCount = DEMO_ALERTS.filter(a => a.level === 'critical').length
  const warningCount  = DEMO_ALERTS.filter(a => a.level === 'warning').length

  // Действие по кнопке сигнала
  const handleAlertAction = (alert) => {
    if (alert.link) {
      navigate(alert.link)
    } else if (alert.divisionId) {
      setOpenDivision(prev => prev === alert.divisionId ? null : alert.divisionId)
      setTimeout(() => {
        document.getElementById('budget-section')?.scrollIntoView({ behavior: 'smooth' })
      }, 100)
    }
  }

  // Раскрыть / свернуть подразделение
  const toggleDivision = (id) => {
    setOpenDivision(prev => prev === id ? null : id)
  }

  return (
    <div>

      {/* ─── Заголовок ─── */}
      <div style={s.pageHeader}>
        <div>
          <h1 style={s.pageTitle}>Обзор региона</h1>
          <p style={s.pageSubtitle}>Иркутский регион</p>
        </div>
        <span style={s.demoBadge}>🛠 Демо-данные</span>
      </div>

      {/* ══════════════════════════════════════════
          БЛОК 1: СИГНАЛЫ
      ══════════════════════════════════════════ */}
      <section style={s.section}>

        <div style={s.sectionHead}>
          <h2 style={s.sectionTitle}>🚨 Сигналы</h2>
          <div style={s.alertBadges}>
            {criticalCount > 0 && (
              <span style={s.badgeCritical}>{criticalCount} критических</span>
            )}
            {warningCount > 0 && (
              <span style={s.badgeWarning}>{warningCount} внимание</span>
            )}
            {criticalCount === 0 && warningCount === 0 && (
              <span style={s.badgeOk}>✅ Всё в порядке</span>
            )}
          </div>
        </div>

        <div style={s.alertGrid}>
          {DEMO_ALERTS.map(alert => (
            <div
              key={alert.id}
              style={{
                ...s.alertCard,
                borderLeftColor: alert.level === 'critical' ? '#dc2626' : '#f59e0b',
                background:      alert.level === 'critical' ? '#fff5f5' : '#fffceb',
              }}
            >
              <div style={s.alertEmoji}>
                {alert.level === 'critical' ? '🔴' : '🟡'}
              </div>
              <div style={s.alertBody}>
                <div style={s.alertTitle}>{alert.title}</div>
                <div style={s.alertDesc}>{alert.desc}</div>
                <button
                  style={{
                    ...s.alertBtn,
                    color: alert.level === 'critical' ? '#dc2626' : '#b45309',
                  }}
                  onClick={() => handleAlertAction(alert)}
                >
                  {alert.action} →
                </button>
              </div>
            </div>
          ))}
        </div>

      </section>

      {/* ══════════════════════════════════════════
          БЛОК 2: БЮДЖЕТ
      ══════════════════════════════════════════ */}
      <section style={s.section} id="budget-section">

        <div style={s.sectionHead}>
          <h2 style={s.sectionTitle}>💰 Бюджет региона</h2>
          <span style={s.budgetSummaryText}>
            {fmt(regionUsed)} из {fmt(regionTotal)}
          </span>
        </div>

        {/* Общий прогресс региона */}
        <div style={s.regionBudgetCard}>
          <div style={s.budgetTopRow}>
            <span style={s.budgetCardLabel}>Использовано по региону</span>
            <span style={{
              ...s.budgetCardPct,
              color: regionPercent >= 80 ? '#dc2626'
                   : regionPercent >= 60 ? '#d97706' : '#059669',
            }}>
              {regionPercent}%
            </span>
          </div>
          <ProgressBar value={regionPercent} />
          <div style={s.budgetCardMeta}>
            Использовано <strong>{fmt(regionUsed)}</strong> ·
            Остаток <strong>{fmt(regionTotal - regionUsed)}</strong> ·
            Лимит <strong>{fmt(regionTotal)}</strong>
          </div>
        </div>

        {/* Список подразделений */}
        <div style={s.divList}>
          {DEMO_DIVISIONS.map(div => {
            const pct        = Math.round((div.budget_used / div.budget_total) * 100)
            const isOpen     = openDivision === div.id
            const hasRisk    = div.risk === 'budget'
            const riskStores = (div.stores || []).filter(st => st.risk)

            return (
              <div
                key={div.id}
                style={{
                  ...s.divCard,
                  ...(hasRisk ? s.divCardRisk : {}),
                  ...(isOpen  ? s.divCardOpen : {}),
                }}
              >
                {/* ── Заголовок подразделения ── */}
                <div style={s.divRow} onClick={() => toggleDivision(div.id)}>

                  <div style={s.divLeft}>
                    <div style={s.divName}>
                      {hasRisk && <span style={s.riskBadgeInline}>⚠ риск</span>}
                      Подр. «{div.name}»
                    </div>
                    <div style={s.divMeta}>
                      {div.executors} исполнителей · {div.tasks_active} активных заданий
                      {riskStores.length > 0 && (
                        <span style={s.divRiskHint}> · {riskStores.length} магазина с риском</span>
                      )}
                    </div>
                  </div>

                  <div style={s.divRight}>
                    <div style={s.divProgress}>
                      <ProgressBar value={pct} warn={pct >= 80} compact />
                      <span style={{
                        ...s.divPct,
                        color: pct >= 80 ? '#dc2626' : '#374151',
                        fontWeight: pct >= 80 ? '800' : '600',
                      }}>
                        {pct}%
                      </span>
                    </div>
                    <span style={s.divBudgetLeft}>ост. {fmt(div.budget_total - div.budget_used)}</span>
                    <span style={s.expandArrow}>{isOpen ? '▲' : '▼'}</span>
                  </div>

                </div>

                {/* ── Раскрытый список магазинов ── */}
                {isOpen && (
                  <div style={s.storeTable}>
                    <div style={s.storeTableHead}>
                      <span style={{ flex: 3 }}>Магазин</span>
                      <span style={{ flex: 2 }}>Бюджет</span>
                      <span style={{ ...s.storeNumHead }}>Задания</span>
                      <span style={{ ...s.storeNumHead }}>Исполн.</span>
                    </div>
                    {div.stores.map(store => {
                      const sPct     = Math.round((store.budget_used / store.budget_total) * 100)
                      const storeRisk = store.risk === 'budget'
                      return (
                        <div
                          key={store.id}
                          style={{
                            ...s.storeRow,
                            ...(storeRisk ? s.storeRowRisk : {}),
                          }}
                        >
                          <div style={{ ...s.storeName, flex: 3 }}>
                            {storeRisk
                              ? <span style={s.storeDot}>🔴</span>
                              : <span style={s.storeDotOk}>🟢</span>
                            }
                            {store.name}
                          </div>
                          <div style={{ flex: 2, display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <ProgressBar value={sPct} warn={sPct >= 80} compact micro />
                            <span style={{
                              fontSize: '12px',
                              fontWeight: '700',
                              minWidth: '32px',
                              color: sPct >= 80 ? '#dc2626' : '#374151',
                            }}>
                              {sPct}%
                            </span>
                          </div>
                          <div style={s.storeNum}>{store.tasks}</div>
                          <div style={s.storeNum}>{store.executors}</div>
                        </div>
                      )
                    })}
                  </div>
                )}

              </div>
            )
          })}
        </div>

      </section>

      {/* ══════════════════════════════════════════
          БЛОК 3: ОБЩАЯ СТАТИСТИКА
      ══════════════════════════════════════════ */}
      <section style={s.section}>

        <h2 style={s.sectionTitle}>📊 Общая статистика</h2>

        <div style={s.statGrid}>
          {[
            { icon: '👥', label: 'Исполнителей',           value: DEMO_STATS.total_executors, link: '/dashboard/users'    },
            { icon: '📋', label: 'Активных заданий',        value: DEMO_STATS.active_tasks,    link: '/dashboard/tasks'    },
            { icon: '✅', label: 'Выплачено в этом месяце', value: fmt(DEMO_STATS.paid_month), link: '/dashboard/payments' },
            { icon: '⏳', label: 'Ожидают выплаты',         value: DEMO_STATS.pending_pay,     link: '/dashboard/payments' },
          ].map(card => (
            <div
              key={card.label}
              style={s.statCard}
              onClick={() => navigate(card.link)}
            >
              <div style={s.statIcon}>{card.icon}</div>
              <div style={s.statValue}>{card.value}</div>
              <div style={s.statLabel}>{card.label}</div>
            </div>
          ))}
        </div>

      </section>

    </div>
  )
}

// =============================================================================
// Компонент прогресс-бара
// =============================================================================
function ProgressBar({ value, warn, compact, micro }) {
  const safeVal = Math.min(100, Math.max(0, value))
  const color   = warn      ? '#ef4444'
                : value >= 60 ? '#f59e0b'
                : '#10b981'
  return (
    <div style={{
      height:      micro ? '4px' : compact ? '6px' : '10px',
      background:  '#ebebeb',
      borderRadius: '4px',
      overflow:    'hidden',
      flex:        compact ? 1 : undefined,
      minWidth:    compact ? (micro ? '60px' : '100px') : undefined,
      marginBottom: compact ? 0 : '8px',
    }}>
      <div style={{
        width:      safeVal + '%',
        height:     '100%',
        background: color,
        borderRadius: '4px',
        transition: 'width .4s ease',
      }} />
    </div>
  )
}

// Форматирование суммы
function fmt(v) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1).replace('.0', '') + ' млн ₽'
  if (v >= 1_000)     return Math.round(v / 1_000) + ' тыс ₽'
  return v + ' ₽'
}

// =============================================================================
// Стили
// =============================================================================
const s = {
  // Заголовок страницы
  pageHeader: {
    display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
    marginBottom: '28px', gap: '12px',
  },
  pageTitle:    { fontSize: '26px', fontWeight: '800', color: '#1a1a1a', margin: 0 },
  pageSubtitle: { fontSize: '14px', color: '#6b7280', marginTop: '4px', marginBottom: 0 },
  demoBadge: {
    background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a',
    borderRadius: '20px', padding: '4px 12px', fontSize: '12px', fontWeight: '700',
    whiteSpace: 'nowrap', alignSelf: 'flex-start',
  },

  // Секции
  section: { marginBottom: '32px' },
  sectionHead: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: '16px', gap: '12px',
  },
  sectionTitle: { fontSize: '17px', fontWeight: '800', color: '#1a1a1a', margin: 0 },

  // Бейджи сигналов
  alertBadges: { display: 'flex', gap: '8px', flexWrap: 'wrap' },
  badgeCritical: {
    background: '#fee2e2', color: '#991b1b', borderRadius: '20px',
    padding: '3px 12px', fontSize: '12px', fontWeight: '800',
  },
  badgeWarning: {
    background: '#fef3c7', color: '#92400e', borderRadius: '20px',
    padding: '3px 12px', fontSize: '12px', fontWeight: '800',
  },
  badgeOk: {
    background: '#d1fae5', color: '#065f46', borderRadius: '20px',
    padding: '3px 12px', fontSize: '12px', fontWeight: '800',
  },

  // Карточки сигналов
  alertGrid: { display: 'flex', flexDirection: 'column', gap: '10px' },
  alertCard: {
    display: 'flex', gap: '14px', alignItems: 'flex-start',
    background: '#fff5f5', borderRadius: '10px',
    borderLeft: '4px solid #dc2626',
    padding: '16px 18px',
    boxShadow: '0 1px 4px rgba(0,0,0,.06)',
  },
  alertEmoji: { fontSize: '18px', flexShrink: 0, marginTop: '1px' },
  alertBody:  { flex: 1 },
  alertTitle: { fontSize: '14px', fontWeight: '700', color: '#1a1a1a', marginBottom: '4px' },
  alertDesc:  { fontSize: '13px', color: '#4b5563', lineHeight: '1.5', marginBottom: '8px' },
  alertBtn: {
    background: 'none', border: 'none', padding: 0,
    fontSize: '13px', fontWeight: '700', cursor: 'pointer', fontFamily: 'inherit',
  },

  // Блок бюджета
  budgetSummaryText: { fontSize: '14px', fontWeight: '700', color: '#374151' },
  regionBudgetCard: {
    background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px',
    padding: '20px 24px', marginBottom: '16px',
    boxShadow: '0 1px 4px rgba(0,0,0,.05)',
  },
  budgetTopRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: '10px',
  },
  budgetCardLabel: { fontSize: '14px', fontWeight: '700', color: '#374151' },
  budgetCardPct:   { fontSize: '28px', fontWeight: '800' },
  budgetCardMeta:  { fontSize: '13px', color: '#6b7280', marginTop: '8px' },

  // Список подразделений
  divList: { display: 'flex', flexDirection: 'column', gap: '8px' },
  divCard: {
    background: '#fff', border: '1.5px solid #e5e7eb',
    borderRadius: '12px', overflow: 'hidden',
    boxShadow: '0 1px 4px rgba(0,0,0,.04)',
    transition: 'border-color .15s',
  },
  divCardRisk: { borderColor: '#fca5a5', background: '#fff' },
  divCardOpen: { borderColor: '#a91d7a' },

  divRow: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 18px', cursor: 'pointer', gap: '16px',
    userSelect: 'none',
  },
  divLeft: { flex: 1, minWidth: 0 },
  divName: {
    fontSize: '14px', fontWeight: '700', color: '#1a1a1a',
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px',
  },
  divMeta: { fontSize: '12px', color: '#6b7280' },
  divRiskHint: { color: '#dc2626', fontWeight: '700' },
  riskBadgeInline: {
    background: '#fee2e2', color: '#dc2626', borderRadius: '4px',
    padding: '1px 7px', fontSize: '11px', fontWeight: '800',
    textTransform: 'uppercase', letterSpacing: '.04em',
  },

  divRight: {
    display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0,
  },
  divProgress: { display: 'flex', alignItems: 'center', gap: '8px', width: '160px' },
  divPct:      { fontSize: '13px', minWidth: '34px', textAlign: 'right' },
  divBudgetLeft:{ fontSize: '12px', color: '#6b7280', whiteSpace: 'nowrap' },
  expandArrow: { fontSize: '11px', color: '#9ca3af', marginLeft: '4px' },

  // Таблица магазинов
  storeTable: { borderTop: '1px solid #f0f0f0' },
  storeTableHead: {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '8px 18px', background: '#f9fafb',
    fontSize: '11px', fontWeight: '700', color: '#9ca3af',
    textTransform: 'uppercase', letterSpacing: '.04em',
  },
  storeNumHead: { width: '64px', textAlign: 'center' },
  storeRow: {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '10px 18px', borderTop: '1px solid #f5f5f5',
    fontSize: '13px', color: '#374151',
    transition: 'background .1s',
  },
  storeRowRisk: { background: '#fff5f5' },
  storeName: {
    display: 'flex', alignItems: 'center', gap: '6px',
    fontWeight: '600', color: '#1a1a1a',
  },
  storeDot:   { fontSize: '10px' },
  storeDotOk: { fontSize: '10px' },
  storeNum:   { width: '64px', textAlign: 'center', fontWeight: '700', fontSize: '13px' },

  // Статистика
  statGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: '16px',
  },
  statCard: {
    background: '#fff', borderRadius: '12px', padding: '20px',
    border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,.04)',
    cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '6px',
    transition: 'box-shadow .15s',
  },
  statIcon:  { fontSize: '22px' },
  statValue: { fontSize: '28px', fontWeight: '800', color: '#1a1a1a', lineHeight: 1 },
  statLabel: { fontSize: '12px', color: '#6b7280', fontWeight: '600' },
}
