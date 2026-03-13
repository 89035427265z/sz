// =============================================================================
// KARI.Самозанятые v2 — Страница аналитики
// Файл: frontend/src/pages/AnalyticsPage.jsx
// =============================================================================
//
// Дашборд аналитики для директора региона и подразделения.
//
// Разделы:
//   1. Плитки KPI (исполнители, задания, выплаты, рейтинг)
//   2. График заданий по дням (Chart.js — линия)
//   3. Топ исполнителей по рейтингу
//   4. Исполнители в зоне риска (3+ штрафа за 90 дней)
//   5. Сравнение магазинов
//
// Цвета KARI:
//   Малиновый: #A01F72
//   Тёмно-синий: #242D4A
//
// =============================================================================

import { useState, useEffect, useCallback } from "react";

// Цвета бренда KARI
const KARI_PINK = "#A01F72";
const KARI_DARK = "#242D4A";

// Имитация API-запроса (в production — настоящий fetch к /api/v1/analytics/...)
async function fetchDashboard(dateFrom, dateTo) {
  // TODO: заменить на реальный API
  await new Promise((r) => setTimeout(r, 600)); // Имитация задержки
  return {
    period_from: dateFrom,
    period_to: dateTo,
    executors_total: 347,
    executors_active: 289,
    executors_new: 23,
    executors_blocked: 12,
    tasks_published: 1240,
    tasks_completed: 1087,
    tasks_cancelled: 58,
    tasks_completion_rate: 87.7,
    payments_total_rub: 4250000,
    payments_count: 1087,
    avg_task_cost: 3909,
    avg_rating: 4.3,
    penalties_issued: 34,
    stop_list_entries: 8,
  };
}

async function fetchExecutorStats() {
  await new Promise((r) => setTimeout(r, 400));
  return {
    top_by_rating: [
      { executor_id: "1", name: "Иванов А.С.", avg_score: 4.9, total_ratings: 42 },
      { executor_id: "2", name: "Петрова М.И.", avg_score: 4.8, total_ratings: 37 },
      { executor_id: "3", name: "Сидоров К.О.", avg_score: 4.7, total_ratings: 55 },
      { executor_id: "4", name: "Козлова Е.В.", avg_score: 4.7, total_ratings: 28 },
      { executor_id: "5", name: "Новиков Д.Р.", avg_score: 4.6, total_ratings: 61 },
    ],
    low_rating: [
      { executor_id: "10", name: "Попов В.Н.", avg_score: 2.4, total_ratings: 8 },
      { executor_id: "11", name: "Фёдоров А.П.", avg_score: 2.7, total_ratings: 6 },
    ],
    at_risk: [
      { executor_id: "20", name: "Орлов И.С.", penalty_count_90d: 4 },
      { executor_id: "21", name: "Лебедев Р.В.", penalty_count_90d: 3 },
      { executor_id: "22", name: "Зайцев К.М.", penalty_count_90d: 3 },
    ],
  };
}

// Данные для мини-графика (задания по дням за последние 14 дней)
function generateChartData() {
  const data = [];
  const today = new Date();
  for (let i = 13; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    data.push({
      date: d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }),
      completed: Math.floor(Math.random() * 40 + 60),
      cancelled: Math.floor(Math.random() * 5),
    });
  }
  return data;
}

// =============================================================================
// ВСПОМОГАТЕЛЬНЫЕ КОМПОНЕНТЫ
// =============================================================================

// Плитка KPI
function KpiCard({ label, value, sub, color = KARI_PINK, icon }) {
  return (
    <div style={{
      background: "white",
      borderRadius: 12,
      padding: "20px 24px",
      boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      borderLeft: `4px solid ${color}`,
      display: "flex",
      flexDirection: "column",
      gap: 4,
    }}>
      <div style={{ fontSize: 24 }}>{icon}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: KARI_DARK }}>{value}</div>
      <div style={{ fontSize: 13, color: "#666" }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: color, fontWeight: 600 }}>{sub}</div>}
    </div>
  );
}

// Строка в таблице топ-исполнителей
function RatingRow({ rank, name, score, ratings }) {
  const stars = "⭐".repeat(Math.round(score));
  return (
    <tr style={{ borderBottom: "1px solid #f0f0f0" }}>
      <td style={{ padding: "10px 12px", color: "#999", fontSize: 13 }}>{rank}</td>
      <td style={{ padding: "10px 12px", fontWeight: 600 }}>{name}</td>
      <td style={{ padding: "10px 12px" }}>
        <span style={{ color: "#f59e0b", fontSize: 14 }}>{stars}</span>
        <span style={{ marginLeft: 6, fontWeight: 700 }}>{score.toFixed(1)}</span>
      </td>
      <td style={{ padding: "10px 12px", color: "#666", fontSize: 13 }}>{ratings} отзывов</td>
    </tr>
  );
}

// Строка риск-исполнителя
function RiskRow({ name, penalties }) {
  const color = penalties >= 4 ? "#dc2626" : "#f59e0b";
  const label = penalties >= 5 ? "Автоблокировка" : penalties >= 3 ? "HR проверка" : "Внимание";
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "10px 0",
      borderBottom: "1px solid #f0f0f0",
    }}>
      <span style={{ fontWeight: 500 }}>{name}</span>
      <span style={{
        background: color + "20",
        color,
        padding: "3px 10px",
        borderRadius: 20,
        fontSize: 12,
        fontWeight: 700,
      }}>
        {penalties} штрафа · {label}
      </span>
    </div>
  );
}

// Простой SVG-график заданий по дням
function SimpleChart({ data }) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.completed)) + 10;
  const W = 600, H = 120, PAD = 20;
  const w = (W - PAD * 2) / (data.length - 1);

  const points = data.map((d, i) => ({
    x: PAD + i * w,
    y: H - PAD - ((d.completed / max) * (H - PAD * 2)),
    val: d.completed,
    date: d.date,
  }));

  const pathD = points.map((p, i) =>
    `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`
  ).join(" ");

  const areaD = pathD +
    ` L${points[points.length-1].x.toFixed(1)},${H - PAD}` +
    ` L${points[0].x.toFixed(1)},${H - PAD} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: 120 }}>
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={KARI_PINK} stopOpacity="0.3" />
          <stop offset="100%" stopColor={KARI_PINK} stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Сетка */}
      {[0.25, 0.5, 0.75, 1].map((t) => (
        <line
          key={t}
          x1={PAD} y1={PAD + (1 - t) * (H - PAD * 2)}
          x2={W - PAD} y2={PAD + (1 - t) * (H - PAD * 2)}
          stroke="#e5e7eb" strokeWidth="1"
        />
      ))}
      {/* Заливка */}
      <path d={areaD} fill="url(#g)" />
      {/* Линия */}
      <path d={pathD} fill="none" stroke={KARI_PINK} strokeWidth="2.5" strokeLinejoin="round" />
      {/* Точки */}
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill={KARI_PINK} />
      ))}
      {/* Подписи дат (каждые 2 дня) */}
      {points.filter((_, i) => i % 2 === 0).map((p, i) => (
        <text key={i} x={p.x} y={H - 2} textAnchor="middle"
          fill="#999" fontSize="9">
          {p.date}
        </text>
      ))}
    </svg>
  );
}

// =============================================================================
// ГЛАВНЫЙ КОМПОНЕНТ
// =============================================================================

export default function AnalyticsPage() {
  // Период фильтрации
  const today = new Date().toISOString().split("T")[0];
  const monthStart = today.slice(0, 7) + "-01";
  const [dateFrom, setDateFrom] = useState(monthStart);
  const [dateTo, setDateTo] = useState(today);

  // Данные
  const [summary, setSummary] = useState(null);
  const [executorStats, setExecutorStats] = useState(null);
  const [chartData] = useState(generateChartData());
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, e] = await Promise.all([
        fetchDashboard(dateFrom, dateTo),
        fetchExecutorStats(),
      ]);
      setSummary(s);
      setExecutorStats(e);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  // Форматирование суммы в рублях
  const rub = (n) =>
    n >= 1_000_000
      ? `${(n / 1_000_000).toFixed(1)} млн ₽`
      : n >= 1000
      ? `${(n / 1000).toFixed(0)} тыс ₽`
      : `${n} ₽`;

  return (
    <div style={{ padding: "24px 32px", fontFamily: "Nunito, sans-serif", maxWidth: 1200 }}>
      {/* ---- Заголовок + Фильтр периода ---- */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, color: KARI_DARK, fontSize: 24 }}>📊 Аналитика</h1>
          <p style={{ margin: "4px 0 0", color: "#666", fontSize: 14 }}>
            Ключевые метрики платформы самозанятых
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ fontSize: 13, color: "#666" }}>Период:</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", fontSize: 13 }}
          />
          <span style={{ color: "#999" }}>—</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", fontSize: 13 }}
          />
          <button
            onClick={load}
            style={{
              padding: "7px 16px",
              background: KARI_PINK,
              color: "white",
              border: "none",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Обновить
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", color: "#999", padding: 80 }}>
          ⏳ Загрузка данных...
        </div>
      ) : (
        <>
          {/* ---- KPI плитки ---- */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16,
            marginBottom: 32,
          }}>
            <KpiCard icon="👥" label="Исполнителей всего" value={summary.executors_total}
              sub={`+${summary.executors_new} новых`} />
            <KpiCard icon="✅" label="Заданий выполнено" value={summary.tasks_completed}
              sub={`${summary.tasks_completion_rate}% выполнения`} color="#16a34a" />
            <KpiCard icon="💰" label="Выплачено" value={rub(summary.payments_total_rub)}
              sub={`${summary.payments_count} транзакций`} color="#0891b2" />
            <KpiCard icon="⭐" label="Средний рейтинг" value={summary.avg_rating.toFixed(1)}
              sub="из 5 звёзд" color="#f59e0b" />
            <KpiCard icon="🚫" label="Заблокированных" value={summary.executors_blocked}
              sub={`${summary.stop_list_entries} в стоп-листе`} color="#dc2626" />
            <KpiCard icon="⚠️" label="Штрафов выписано" value={summary.penalties_issued}
              sub="за период" color="#ea580c" />
          </div>

          {/* ---- График заданий по дням ---- */}
          <div style={{
            background: "white",
            borderRadius: 12,
            padding: "20px 24px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
            marginBottom: 24,
          }}>
            <h3 style={{ margin: "0 0 16px", color: KARI_DARK, fontSize: 16 }}>
              📈 Выполненные задания — последние 14 дней
            </h3>
            <SimpleChart data={chartData} />
          </div>

          {/* ---- Два блока рядом: Топ + Риски ---- */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>

            {/* Топ исполнителей */}
            <div style={{
              background: "white",
              borderRadius: 12,
              padding: "20px 24px",
              boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
            }}>
              <h3 style={{ margin: "0 0 16px", color: KARI_DARK, fontSize: 16 }}>
                🏆 Топ исполнителей по рейтингу
              </h3>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                <thead>
                  <tr style={{ background: "#f9fafb", color: "#6b7280", fontSize: 12, textTransform: "uppercase" }}>
                    <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>#</th>
                    <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Исполнитель</th>
                    <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Оценка</th>
                    <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Отзывы</th>
                  </tr>
                </thead>
                <tbody>
                  {executorStats.top_by_rating.map((e, i) => (
                    <RatingRow key={e.executor_id} rank={i + 1}
                      name={e.name} score={e.avg_score} ratings={e.total_ratings} />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Зона риска */}
            <div style={{
              background: "white",
              borderRadius: 12,
              padding: "20px 24px",
              boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
            }}>
              <h3 style={{ margin: "0 0 4px", color: KARI_DARK, fontSize: 16 }}>
                ⚠️ Зона риска
              </h3>
              <p style={{ margin: "0 0 16px", color: "#666", fontSize: 12 }}>
                3+ штрафа за последние 90 дней
              </p>
              {executorStats.at_risk.length === 0 ? (
                <div style={{ color: "#16a34a", textAlign: "center", padding: 24 }}>
                  ✅ Нарушителей нет
                </div>
              ) : (
                executorStats.at_risk.map((e) => (
                  <RiskRow key={e.executor_id} name={e.name}
                    penalties={e.penalty_count_90d} />
                ))
              )}

              {executorStats.low_rating.length > 0 && (
                <>
                  <h4 style={{ margin: "20px 0 8px", color: "#dc2626", fontSize: 14 }}>
                    📉 Низкий рейтинг (&lt; 3.0)
                  </h4>
                  {executorStats.low_rating.map((e) => (
                    <div key={e.executor_id} style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "8px 0",
                      borderBottom: "1px solid #f0f0f0",
                      fontSize: 14,
                    }}>
                      <span>{e.name}</span>
                      <span style={{ color: "#dc2626", fontWeight: 700 }}>
                        ⭐ {e.avg_score.toFixed(1)} ({e.total_ratings} отзывов)
                      </span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          {/* ---- Итоговые рекомендации ---- */}
          <div style={{
            background: KARI_DARK,
            color: "white",
            borderRadius: 12,
            padding: "20px 28px",
          }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>💡 Рекомендации</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, fontSize: 14 }}>
              <div>
                <div style={{ color: KARI_PINK, fontWeight: 700, marginBottom: 4 }}>Исполнители</div>
                <div style={{ color: "#ccc" }}>
                  {summary.executors_blocked > 0
                    ? `${summary.executors_blocked} заблокированных — проверьте через HR`
                    : "Всё в порядке"}
                </div>
              </div>
              <div>
                <div style={{ color: KARI_PINK, fontWeight: 700, marginBottom: 4 }}>Задания</div>
                <div style={{ color: "#ccc" }}>
                  Выполняемость {summary.tasks_completion_rate}%
                  {summary.tasks_completion_rate < 85
                    ? " — ниже целевого (85%)" : " — в норме ✓"}
                </div>
              </div>
              <div>
                <div style={{ color: KARI_PINK, fontWeight: 700, marginBottom: 4 }}>Качество</div>
                <div style={{ color: "#ccc" }}>
                  Рейтинг {summary.avg_rating.toFixed(1)} ⭐
                  {summary.avg_rating >= 4.0 ? " — отлично ✓" : " — нужно улучшить"}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
