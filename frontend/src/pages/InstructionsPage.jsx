// =============================================================================
// KARI.Самозанятые — Раздел «Инструкции»
// =============================================================================
// Показывает пошаговые инструкции в зависимости от роли пользователя.
// Роль определяется автоматически из контекста авторизации.

import { useState } from 'react'
import { useAuth } from '../hooks/useAuth.js'

// ── Стили ──
const s = {
  page:        { fontFamily: 'Nunito, sans-serif' },
  header:      { marginBottom: '28px' },
  pageTitle:   { fontSize: '24px', fontWeight: '800', color: '#242D4A', margin: '0 0 6px' },
  pageSub:     { fontSize: '14px', color: '#6b7280' },

  // Вкладки тем
  tabs:        { display: 'flex', gap: '8px', marginBottom: '24px', flexWrap: 'wrap' },
  tab:         { padding: '8px 18px', borderRadius: '20px', borderWidth: '2px', borderStyle: 'solid', borderColor: '#e5e7eb', background: '#fff', color: '#6b7280', fontWeight: '700', fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit', transition: 'all .15s' },
  tabActive:   { background: '#A01F72', borderColor: '#A01F72', color: '#fff' },

  // Карточки
  card:        { background: '#fff', borderRadius: '12px', padding: '24px', marginBottom: '16px', boxShadow: '0 1px 4px rgba(0,0,0,.07)' },
  cardTitle:   { fontSize: '17px', fontWeight: '800', color: '#242D4A', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },

  // Шаги
  steps:       { display: 'flex', flexDirection: 'column', gap: '14px' },
  step:        { display: 'flex', gap: '14px', alignItems: 'flex-start' },
  stepNum:     { width: '28px', height: '28px', borderRadius: '50%', background: '#f9eef5', color: '#A01F72', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '800', fontSize: '13px', flexShrink: 0, marginTop: '2px' },
  stepBody:    { flex: 1 },
  stepTitle:   { fontSize: '14px', fontWeight: '700', color: '#242D4A', marginBottom: '3px' },
  stepText:    { fontSize: '13px', color: '#6b7280', lineHeight: '1.5' },

  // Алерты
  alertGreen:  { background: '#dcfce7', color: '#15803d', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', marginBottom: '12px', display: 'flex', gap: '10px', alignItems: 'flex-start' },
  alertOrange: { background: '#fef3c7', color: '#92400e', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', marginBottom: '12px', display: 'flex', gap: '10px', alignItems: 'flex-start' },
  alertBlue:   { background: '#dbeafe', color: '#1e40af', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', marginBottom: '12px', display: 'flex', gap: '10px', alignItems: 'flex-start' },
  alertIcon:   { fontSize: '16px', flexShrink: 0 },

  // Сетка
  grid2:       { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' },

  // Таблица статусов
  table:       { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th:          { background: '#242D4A', color: '#fff', padding: '8px 12px', textAlign: 'left', fontWeight: '700' },
  td:          { padding: '9px 12px', borderBottom: '1px solid #e5e7eb' },

  // Бейджи
  badgeGreen:  { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', background: '#dcfce7', color: '#16a34a', fontWeight: '700', fontSize: '12px' },
  badgeOrange: { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', background: '#fef3c7', color: '#d97706', fontWeight: '700', fontSize: '12px' },
  badgeBlue:   { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', background: '#dbeafe', color: '#2563eb', fontWeight: '700', fontSize: '12px' },
  badgeKari:   { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', background: '#f9eef5', color: '#A01F72', fontWeight: '700', fontSize: '12px' },
  badgeGray:   { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', background: '#f3f4f6', color: '#6b7280', fontWeight: '700', fontSize: '12px' },
  badgeRed:    { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', background: '#fee2e2', color: '#dc2626', fontWeight: '700', fontSize: '12px' },

  // FAQ
  faqItem:     { background: '#fff', borderRadius: '10px', marginBottom: '10px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,.06)' },
  faqQ:        { padding: '14px 18px', fontWeight: '700', color: '#242D4A', fontSize: '14px', borderLeft: '4px solid #A01F72', background: '#f9eef5', cursor: 'pointer', userSelect: 'none' },
  faqA:        { padding: '12px 18px', fontSize: '13px', color: '#374151', lineHeight: '1.6' },

  // Контакты
  contactsRow: { display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '8px' },
  contactBox:  { background: '#242D4A', color: '#fff', borderRadius: '10px', padding: '16px 20px', textAlign: 'center', flex: '1', minWidth: '140px' },
  contactIcon: { fontSize: '22px', marginBottom: '6px' },
  contactLbl:  { fontSize: '10px', opacity: .6, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: '3px' },
  contactVal:  { fontSize: '13px', fontWeight: '800', color: '#fff', textDecoration: 'none' },

  divider:     { height: '1px', background: '#e5e7eb', margin: '16px 0' },
}

// ── FAQ-компонент ──
function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={s.faqItem}>
      <div style={s.faqQ} onClick={() => setOpen(o => !o)}>
        {open ? '▼' : '▶'} &nbsp;{q}
      </div>
      {open && <div style={s.faqA}>{a}</div>}
    </div>
  )
}

// ── Шаг ──
function Step({ n, title, text }) {
  return (
    <div style={s.step}>
      <div style={s.stepNum}>{n}</div>
      <div style={s.stepBody}>
        <div style={s.stepTitle}>{title}</div>
        <div style={s.stepText}>{text}</div>
      </div>
    </div>
  )
}

// =============================================================================
// СОДЕРЖИМОЕ ДЛЯ КАЖДОЙ РОЛИ
// =============================================================================

// ── Директор магазина ──
function StoreDirectorInstructions() {
  const topics = ['Задания', 'Приёмка', 'Исполнители', 'Статусы', 'FAQ']
  const [tab, setTab] = useState('Задания')

  return (
    <>
      <div style={s.tabs}>
        {topics.map(t => (
          <button key={t} style={tab === t ? { ...s.tab, ...s.tabActive } : s.tab} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Задания' && (
        <>
          <div style={s.card}>
            <div style={s.cardTitle}>📋 Как создать задание для самозанятого</div>
            <div style={s.steps}>
              <Step n="1" title="Откройте раздел «Задания»" text="В боковом меню нажмите «Задания». Нажмите кнопку «+ Создать задание» в правом верхнем углу." />
              <Step n="2" title="Заполните карточку задания" text="Укажите: название, описание работ, адрес магазина, сумму оплаты (от 100 до 100 000 руб), дату выполнения, количество часов, сколько исполнителей нужно." />
              <Step n="3" title="Опубликуйте задание" text="Нажмите «Создать». Задание появится на бирже — самозанятые увидят его в мобильном приложении и смогут взять." />
            </div>
            <div style={{ ...s.divider }} />
            <div style={s.alertOrange}>
              <div style={s.alertIcon}>⚠️</div>
              <div><b>Минимум за 24 часа</b> до выполнения — самозанятым нужно время найти и взять задание.</div>
            </div>
          </div>

          <div style={s.card}>
            <div style={s.cardTitle}>✏️ Редактирование и отмена задания</div>
            <div style={s.steps}>
              <Step n="1" title="Редактирование возможно только для заданий со статусом «Доступно»" text="Если исполнитель уже взял задание — менять сумму и дату нельзя. Можно только добавить комментарий." />
              <Step n="2" title="Отмена задания" text="Нажмите «⋯» → «Отменить». Если у задания есть исполнитель — он получит уведомление об отмене." />
            </div>
          </div>
        </>
      )}

      {tab === 'Приёмка' && (
        <>
          <div style={s.alertBlue}>
            <div style={s.alertIcon}>ℹ️</div>
            <div>Когда самозанятый сдаёт задание, вы получаете уведомление. Нужно проверить фотоотчёт и принять или отклонить работу.</div>
          </div>

          <div style={s.card}>
            <div style={s.cardTitle}>✅ Как принять выполненную работу</div>
            <div style={s.steps}>
              <Step n="1" title="Раздел «Приёмка работ»" text="В меню нажмите «Приёмка работ» — там все задания со статусом «На проверке»." />
              <Step n="2" title="Просмотрите фотоотчёт" text="Откройте задание. Проверьте фотографии, геометку (исполнитель был в магазине?), комментарий исполнителя." />
              <Step n="3" title="Примите или отклоните работу" text="Нажмите «Принять работу» — выплата запустится автоматически. Или «Отклонить» — введите причину отказа, исполнитель увидит её в приложении." />
            </div>
            <div style={s.divider} />
            <div style={s.alertGreen}>
              <div style={s.alertIcon}>✅</div>
              <div><b>После приёмки</b> — оплата на карту исполнителя переводится в течение 1–2 рабочих дней. Чек в ФНС формируется автоматически.</div>
            </div>
          </div>

          <div style={s.card}>
            <div style={s.cardTitle}>❌ Когда можно отклонить работу</div>
            <div style={s.steps}>
              <Step n="1" title="Работа не выполнена или выполнена некачественно" text="На фото не видно результата. Укажите это в причине отказа." />
              <Step n="2" title="Фото не соответствуют заданию" text="Скриншот чужой работы, нечёткие фото. Укажите конкретную причину." />
              <Step n="3" title="Исполнитель не был в магазине" text="Геометка показывает другой адрес. Обязательно укажите это — важно для контроля." />
            </div>
            <div style={s.divider} />
            <div style={s.alertOrange}>
              <div style={s.alertIcon}>⚠️</div>
              <div><b>Не злоупотребляйте отклонениями.</b> При спорных ситуациях звоните куратору — он поможет разобраться.</div>
            </div>
          </div>
        </>
      )}

      {tab === 'Исполнители' && (
        <div style={s.card}>
          <div style={s.cardTitle}>👥 Работа с исполнителями</div>
          <div style={s.steps}>
            <Step n="1" title="Просмотр списка" text="Раздел «Исполнители» — все самозанятые, которые работали с вашим магазином. Статус ФНС, рейтинг, история заданий." />
            <Step n="2" title="Карточка исполнителя" text="Нажмите на имя — откроется профиль: ИНН, статус ФНС, количество выполненных заданий, история выплат." />
            <Step n="3" title="Статус ФНС" text="Зелёный — самозанятый активен, можно работать. Красный — статус аннулирован, создавать выплату нельзя. Система предупредит вас автоматически." />
          </div>
          <div style={s.divider} />
          <div style={s.alertBlue}>
            <div style={s.alertIcon}>💡</div>
            <div>Нельзя напрямую «пригласить» конкретного исполнителя — задания публикуются на общей бирже. Исполнитель сам выбирает задания.</div>
          </div>
        </div>
      )}

      {tab === 'Статусы' && (
        <div style={s.card}>
          <div style={s.cardTitle}>🔄 Статусы заданий</div>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Статус</th>
                <th style={s.th}>Что значит</th>
                <th style={s.th}>Ваши действия</th>
              </tr>
            </thead>
            <tbody>
              {[
                [<span style={s.badgeBlue}>Доступно</span>,       'Задание опубликовано, ждёт исполнителя', 'Ничего — ждёте'],
                [<span style={s.badgeOrange}>В работе</span>,     'Исполнитель взял задание',               'Ничего — ждёте сдачи'],
                [<span style={s.badgeKari}>На проверке</span>,    'Исполнитель сдал фотоотчёт',             '⚡ Проверьте и примите/отклоните'],
                [<span style={s.badgeGreen}>Выполнено</span>,     'Работа принята, выплата запущена',       'Всё готово ✅'],
                [<span style={s.badgeRed}>Отклонено</span>,       'Вы не приняли работу',                   'Исполнитель видит причину'],
                [<span style={s.badgeGray}>Отменено</span>,       'Задание отменили вы',                    '—'],
              ].map(([badge, what, action], i) => (
                <tr key={i} style={{ background: i % 2 ? '#fafafa' : '#fff' }}>
                  <td style={s.td}>{badge}</td>
                  <td style={s.td}>{what}</td>
                  <td style={s.td}>{action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'FAQ' && (
        <>
          <FaqItem q="Исполнитель взял задание, но не пришёл — что делать?" a="Свяжитесь с исполнителем напрямую (номер телефона в его профиле). Если связаться не удаётся — отклоните работу с причиной «Исполнитель не явился» и позвоните куратору." />
          <FaqItem q="Сколько задний можно создать в день?" a="Ограничений нет. Создавайте столько, сколько нужно магазину." />
          <FaqItem q="Могу ли я задать конкретную цену для конкретного исполнителя?" a="Нет — цена в задании единая для всех. Но вы можете создать отдельное задание с нужными условиями." />
          <FaqItem q="Где посмотреть историю всех выплат по моему магазину?" a="Раздел «Задания» → фильтр «Выполненные». Или обратитесь к HRD/бухгалтерии — у них раздел «Выплаты» с полной историей." />
          <FaqItem q="Что значит «Статус ФНС неактивен»?" a="Самозанятый снялся с учёта или его аннулировали. Система это обнаружила при ежедневной проверке. Работать с ним и выплачивать деньги нельзя — это нарушение. Свяжитесь с HRD." />
        </>
      )}
    </>
  )
}

// ── Директор региона ──
function RegionalDirectorInstructions() {
  const topics = ['Обзор', 'Бюджет', 'Реестр выплат', 'ФНС', 'FAQ']
  const [tab, setTab] = useState('Обзор')

  return (
    <>
      <div style={s.tabs}>
        {topics.map(t => (
          <button key={t} style={tab === t ? { ...s.tab, ...s.tabActive } : s.tab} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Обзор' && (
        <>
          <div style={s.card}>
            <div style={s.cardTitle}>📊 Что видно на дашборде</div>
            <div style={s.steps}>
              <Step n="1" title="Сигналы тревоги (вверху)" text="Критические проблемы: статус ФНС аннулирован, лимит дохода превышен, просроченные задания. Требуют вашего внимания." />
              <Step n="2" title="Бюджетный контроль" text="Израсходовано / осталось по региону и подразделениям. При достижении 80% — автоматическое предупреждение." />
              <Step n="3" title="Drill-down по магазинам" text="Нажмите на подразделение → откроется список магазинов. Нажмите на магазин → задания, выплаты, исполнители." />
            </div>
          </div>

          <div style={s.card}>
            <div style={s.cardTitle}>👥 Управление доступами</div>
            <div style={s.steps}>
              <Step n="1" title="Раздел «Исполнители»" text="Полный список всех самозанятых в регионе. Статус ФНС, рейтинг, лимит дохода, история." />
              <Step n="2" title="Делегирование прав" text="Вы можете назначить директора подразделения и магазина. Раздел «Исполнители» → выбрать пользователя → изменить роль." />
              <Step n="3" title="Бюджетные лимиты" text="Установите лимит расходов на подразделение или магазин. При превышении 80% — система предупредит директора." />
            </div>
          </div>
        </>
      )}

      {tab === 'Бюджет' && (
        <div style={s.card}>
          <div style={s.cardTitle}>💼 Контроль бюджета региона</div>
          <div style={s.steps}>
            <Step n="1" title="Установить лимит" text="Дашборд → карточка подразделения → «Изменить лимит». Введите сумму в рублях. Лимит распространяется на все задания этого подразделения." />
            <Step n="2" title="Предупреждение 80%" text="Когда расходовано 80% лимита — директор подразделения получает уведомление. Вы видите жёлтый индикатор на дашборде." />
            <Step n="3" title="Превышение лимита" text="При достижении 100% — новые задания в этом подразделении нельзя создавать. Нужно увеличить лимит или перераспределить бюджет." />
          </div>
          <div style={s.divider} />
          <div style={s.alertOrange}>
            <div style={s.alertIcon}>⚠️</div>
            <div><b>Лимит — не блокировка уже взятых заданий.</b> Если задание взяли до превышения лимита — выплата по нему пройдёт.</div>
          </div>
        </div>
      )}

      {tab === 'Реестр выплат' && (
        <>
          <div style={s.alertBlue}>
            <div style={s.alertIcon}>📄</div>
            <div>Реестр — массовая выплата до <b>1 000 исполнителей</b> через Excel-файл. Используется для разовых проектов, переоценок, инвентаризаций.</div>
          </div>
          <div style={s.card}>
            <div style={s.cardTitle}>📥 Как загрузить реестр выплат</div>
            <div style={s.steps}>
              <Step n="1" title="Раздел «Выплаты» → вкладка «Реестры»" text="Нажмите «+ Загрузить реестр»." />
              <Step n="2" title="Подготовьте Excel-файл" text="Формат: 6 столбцов — ИНН (12 цифр), ФИО, Описание услуги, Сумма, Дата выполнения (ДД.ММ.ГГГГ), Примечание. Строка 1 — заголовок, данные — со строки 2." />
              <Step n="3" title="Загрузите файл" text="Перетащите файл или выберите через кнопку. Система автоматически проверит каждую строку (статус ФНС, лимит дохода, дубли, суммы)." />
              <Step n="4" title="Проверьте результат валидации" text="Зелёные строки — ✅ можно оплатить. Красные — ❌ ошибка, нужно исправить. Скачайте отчёт с ошибками." />
              <Step n="5" title="Подтвердите реестр" text="Нажмите «Утвердить реестр». Система поставит все выплаты в очередь — деньги придут на карты в течение 1–2 рабочих дней." />
            </div>
          </div>
        </>
      )}

      {tab === 'ФНС' && (
        <div style={s.card}>
          <div style={s.cardTitle}>🏛️ Мониторинг ФНС и чеков</div>
          <div style={s.steps}>
            <Step n="1" title="Раздел «ФНС / Чеки»" text="Статусы всех самозанятых. Каждый день в 07:00 система автоматически проверяет статусы в ФНС «Мой налог»." />
            <Step n="2" title="Аннулированные чеки" text="Вкладка «Аннулирования» — список чеков, которые самозанятые аннулировали после выплаты. Требует расследования и возможного возврата средств." />
            <Step n="3" title="Экспорт для бухгалтерии" text="Кнопка «Экспорт XML» — выгрузка реестра выплат в формате для 1С:ЗУП." />
          </div>
          <div style={s.divider} />
          <div style={s.alertGreen}>
            <div style={s.alertIcon}>✅</div>
            <div>Чеки формируются автоматически при каждой выплате. Самостоятельно ничего делать не нужно — только контролировать аннулирования.</div>
          </div>
        </div>
      )}

      {tab === 'FAQ' && (
        <>
          <FaqItem q="Как добавить нового директора магазина в систему?" a="Раздел «Исполнители» → «Добавить пользователя» → укажите телефон, ФИО, выберите роль «Директор магазина» и привяжите к нужному магазину. Пользователь войдёт через SMS на этот номер." />
          <FaqItem q="Что делать если самозанятый превысил лимит 2 400 000 руб/год?" a="Система автоматически заблокирует выплату и пометит строку в реестре ошибкой. Свяжитесь с исполнителем — ему нужно открыть ИП или дождаться следующего года. Задания за него брать нельзя." />
          <FaqItem q="Как посмотреть все выплаты за период?" a="Раздел «Выплаты» → фильтр по дате. Кнопка «Экспорт» — скачать в Excel или XML для 1С." />
          <FaqItem q="Совкомбанк не провёл выплату — что делать?" a="Система автоматически повторит выплату до 3 раз. Если после 3 попыток всё равно ошибка — в выплате будет кнопка «Обратиться в поддержку». Передайте ID транзакции в Совкомбанк." />
        </>
      )}
    </>
  )
}

// ── Директор подразделения ──
function DivisionDirectorInstructions() {
  const topics = ['Магазины', 'Бюджет', 'Задания', 'FAQ']
  const [tab, setTab] = useState('Магазины')

  return (
    <>
      <div style={s.tabs}>
        {topics.map(t => (
          <button key={t} style={tab === t ? { ...s.tab, ...s.tabActive } : s.tab} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Магазины' && (
        <div style={s.card}>
          <div style={s.cardTitle}>🏪 Обзор магазинов подразделения</div>
          <div style={s.steps}>
            <Step n="1" title="Главная страница — карточки магазинов" text="Каждая карточка: название, адрес, активные задания, расходы этого месяца, использование бюджета." />
            <Step n="2" title="Drill-down в магазин" text="Нажмите на карточку → откроются задания конкретного магазина, список исполнителей, выплаты." />
            <Step n="3" title="Сигналы тревоги" text="Если у магазина превышен бюджет или есть проблема с ФНС — карточка выделится красным. Нажмите для деталей." />
          </div>
        </div>
      )}

      {tab === 'Бюджет' && (
        <div style={s.card}>
          <div style={s.cardTitle}>💼 Контроль бюджета подразделения</div>
          <div style={s.steps}>
            <Step n="1" title="Ваш лимит установил директор региона" text="Вы видите общий лимит подразделения и сколько уже потрачено. Изменить лимит может только директор региона." />
            <Step n="2" title="Предупреждение при 80%" text="Вы получите уведомление в системе и на email. Нужно проконтролировать — не создавать лишних заданий до конца периода или запросить увеличение лимита." />
            <Step n="3" title="Запрос на увеличение лимита" text="Свяжитесь с директором региона. В системе пока нет автоматической заявки — это делается вручную." />
          </div>
        </div>
      )}

      {tab === 'Задания' && (
        <div style={s.card}>
          <div style={s.cardTitle}>📋 Задания по подразделению</div>
          <div style={s.steps}>
            <Step n="1" title="Раздел «Задания» — все задания ваших магазинов" text="Фильтры: по статусу, по магазину, по дате. Вы видите задания всех магазинов подразделения." />
            <Step n="2" title="Вы не создаёте задания" text="Задания создают директора магазинов. Вы контролируете и видите общую картину." />
            <Step n="3" title="Задания на проверке" text="Фильтр «На проверке» — задания, которые ждут приёмки от директора магазина. Если директор магазина не реагирует — напомните ему." />
          </div>
        </div>
      )}

      {tab === 'FAQ' && (
        <>
          <FaqItem q="Директор магазина создал задание с неправильной суммой — как исправить?" a="Директор магазина может отредактировать задание, пока исполнитель его не взял. Если взял — только отмена задания и создание нового. Свяжитесь с директором магазина." />
          <FaqItem q="Кто видит мои данные?" a="Директор региона видит всё. Директора других подразделений — не видят ваши данные." />
          <FaqItem q="Как скачать отчёт по выплатам за период?" a="Раздел «Задания» → фильтр по дате и статусу «Выполнено» → кнопка «Экспорт». Или обратитесь к HRD — у них полная аналитика." />
        </>
      )}
    </>
  )
}

// ── HRD / Бухгалтерия ──
function HrdInstructions() {
  const topics = ['Договоры', 'Выплаты', 'Реестр', 'ФНС', 'FAQ']
  const [tab, setTab] = useState('Договоры')

  return (
    <>
      <div style={s.tabs}>
        {topics.map(t => (
          <button key={t} style={tab === t ? { ...s.tab, ...s.tabActive } : s.tab} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Договоры' && (
        <div style={s.card}>
          <div style={s.cardTitle}>📄 Работа с договорами</div>
          <div style={s.steps}>
            <Step n="1" title="Раздел «Договоры»" text="Все договоры ГПХ и акты выполненных работ. Фильтры: по статусу (активен, ожидает подписи, архив), по исполнителю, по дате." />
            <Step n="2" title="Договор подписывается автоматически" text="При первом задании исполнителю отправляется договор. Он подписывает его через SMS-код в мобильном приложении." />
            <Step n="3" title="Акт выполненных работ" text="Формируется автоматически после каждого принятого задания. Подписывается тоже через SMS-код исполнителем." />
            <Step n="4" title="Скачать документ" text="Нажмите на документ → кнопка «Скачать PDF». Документ хранится в системе минимум 5 лет." />
          </div>
          <div style={s.divider} />
          <div style={s.alertBlue}>
            <div style={s.alertIcon}>⚖️</div>
            <div>Подпись через SMS — это <b>ПЭП (Простая Электронная Подпись)</b> согласно 63-ФЗ. Имеет юридическую силу.</div>
          </div>
        </div>
      )}

      {tab === 'Выплаты' && (
        <div style={s.card}>
          <div style={s.cardTitle}>💰 Контроль выплат</div>
          <div style={s.steps}>
            <Step n="1" title="Раздел «Выплаты» — общая история" text="Все выплаты по всем магазинам. Фильтры: по статусу, по дате, по исполнителю, по магазину." />
            <Step n="2" title="Статусы выплат" text="Ожидает → Обрабатывается → Выплачено. При ошибке — система повторяет до 3 раз автоматически." />
            <Step n="3" title="Экспорт для 1С" text="Кнопка «Экспорт XML» — выгрузка в формате для 1С:ЗУП. Кнопка «Экспорт Excel» — для своих таблиц." />
            <Step n="4" title="Аналитика" text="Раздел «Аналитика» — графики: расходы по месяцам, топ магазинов по расходам, динамика количества исполнителей." />
          </div>
        </div>
      )}

      {tab === 'Реестр' && (
        <>
          <div style={s.alertBlue}>
            <div style={s.alertIcon}>📊</div>
            <div>Реестр массовых выплат используется для разовых проектов: переоценка, инвентаризация, промоакции. До <b>1 000 строк</b> в одном файле.</div>
          </div>
          <div style={s.card}>
            <div style={s.cardTitle}>📥 Формат Excel-реестра</div>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>Столбец</th>
                  <th style={s.th}>Содержимое</th>
                  <th style={s.th}>Требования</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['A', 'ИНН исполнителя', '12 цифр, обязательно'],
                  ['B', 'ФИО исполнителя', 'Полное имя'],
                  ['C', 'Описание услуги', 'Что сделано'],
                  ['D', 'Сумма (руб)', 'Число > 0 и ≤ 100 000'],
                  ['E', 'Дата выполнения', 'ДД.ММ.ГГГГ'],
                  ['F', 'Примечание', 'Необязательно'],
                ].map(([col, cont, req], i) => (
                  <tr key={col} style={{ background: i % 2 ? '#fafafa' : '#fff' }}>
                    <td style={{ ...s.td, fontWeight: '800' }}>{col}</td>
                    <td style={s.td}>{cont}</td>
                    <td style={s.td}>{req}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ ...s.divider }} />
            <div style={s.alertOrange}>
              <div style={s.alertIcon}>⚠️</div>
              <div>Строка 1 — <b>заголовок</b> (его содержимое не важно). Данные начинаются со строки 2.</div>
            </div>
          </div>

          <div style={s.card}>
            <div style={s.cardTitle}>🔍 Что проверяет система при валидации</div>
            <div style={s.steps}>
              <Step n="1" title="Статус ФНС" text="Самозанятый зарегистрирован и активен. Если нет — строка получает ошибку." />
              <Step n="2" title="Лимит дохода" text="Не превышен ли порог 2 400 000 руб/год у исполнителя." />
              <Step n="3" title="Дубли" text="Нет ли уже выплаты этому ИНН за эту дату." />
              <Step n="4" title="Корректность суммы" text="Больше нуля и не превышает 100 000 руб." />
              <Step n="5" title="Бюджет" text="Зарезервировано. Реальная проверка против лимита — в следующей версии." />
            </div>
          </div>
        </>
      )}

      {tab === 'ФНС' && (
        <div style={s.card}>
          <div style={s.cardTitle}>🏛️ ФНС и чеки</div>
          <div style={s.steps}>
            <Step n="1" title="Автоматическая проверка" text="Каждый день в 07:00 система проверяет статус всех самозанятых в ФНС «Мой налог». Изменения отображаются в разделе «ФНС / Чеки»." />
            <Step n="2" title="Чеки" text="При каждой выплате система автоматически регистрирует чек в ФНС. Вы можете посмотреть и скачать любой чек." />
            <Step n="3" title="Аннулированные чеки" text="Вкладка «Аннулирования» — критически важно! Если исполнитель аннулировал чек — это риск для KARI (налоговые последствия). Требует расследования и возможного удержания." />
            <Step n="4" title="Экспорт для бухгалтерии" text="Кнопка «Экспорт XML» — реестр чеков в формате для 1С:ЗУП." />
          </div>
          <div style={s.divider} />
          <div style={s.alertOrange}>
            <div style={s.alertIcon}>⚠️</div>
            <div><b>Аннулированные чеки нужно отрабатывать в течение 5 рабочих дней.</b> Свяжитесь с самозанятым, восстановите чек или верните сумму выплаты.</div>
          </div>
        </div>
      )}

      {tab === 'FAQ' && (
        <>
          <FaqItem q="Как найти выплату конкретного исполнителя за конкретный месяц?" a="Раздел «Выплаты» → поиск по ФИО или ИНН → фильтр по дате. Или раздел «Аналитика» → профиль исполнителя." />
          <FaqItem q="Нужно ли сдавать отчётность по самозанятым?" a="Нет. Самозанятые сами платят налог через «Мой налог». KARI не является налоговым агентом. Ваша задача — убедиться, что чеки сформированы и не аннулированы." />
          <FaqItem q="Как выгрузить все акты за квартал?" a="Раздел «Договоры» → фильтр «Тип: Акт» → фильтр по дате → «Экспорт PDF» (пакетная выгрузка)." />
          <FaqItem q="Исполнитель говорит, что не получил деньги, но в системе статус «Выплачено»" a="Проверьте ID транзакции Совкомбанка в деталях выплаты. Передайте его в Совкомбанк для трассировки платежа. Обычно задержка — банк-получатель исполнителя." />
          <FaqItem q="Можно ли изменить карту исполнителя для выплат?" a="Нет — исполнитель сам меняет карту в мобильном приложении (Профиль → Реквизиты). Вы не можете менять чужие банковские данные." />
        </>
      )}
    </>
  )
}

// =============================================================================
// ГЛАВНЫЙ КОМПОНЕНТ
// =============================================================================

export default function InstructionsPage() {
  const { user } = useAuth()
  const role = user?.role || 'regional_director'

  const titles = {
    regional_director: { icon: '📊', title: 'Инструкции для директора региона', sub: 'Управление платформой, бюджет, реестры, ФНС' },
    division_director: { icon: '🏢', title: 'Инструкции для директора подразделения', sub: 'Контроль магазинов, бюджет, задания' },
    store_director:    { icon: '🏪', title: 'Инструкции для директора магазина', sub: 'Создание заданий, приёмка работ, исполнители' },
    hrd:               { icon: '📋', title: 'Инструкции для HRD / Бухгалтерии', sub: 'Договоры, выплаты, реестры, ФНС' },
  }

  const { icon, title, sub } = titles[role] || titles.regional_director

  return (
    <div style={s.page}>
      {/* Заголовок */}
      <div style={s.header}>
        <div style={s.pageTitle}>{icon} {title}</div>
        <div style={s.pageSub}>{sub}</div>
      </div>

      {/* Контент по роли */}
      {role === 'store_director'    && <StoreDirectorInstructions />}
      {role === 'regional_director' && <RegionalDirectorInstructions />}
      {role === 'division_director' && <DivisionDirectorInstructions />}
      {role === 'hrd'               && <HrdInstructions />}

      {/* Поддержка (общая для всех) */}
      <div style={s.card}>
        <div style={s.cardTitle}>📞 Поддержка пилота</div>
        <div style={s.contactsRow}>
          <div style={s.contactBox}>
            <div style={s.contactIcon}>📞</div>
            <div style={s.contactLbl}>Горячая линия</div>
            <a href="tel:+73952000000" style={s.contactVal}>+7 (3952) 00-00-00</a>
          </div>
          <div style={s.contactBox}>
            <div style={s.contactIcon}>📧</div>
            <div style={s.contactLbl}>Электронная почта</div>
            <a href="mailto:pilot@kari.com" style={s.contactVal}>pilot@kari.com</a>
          </div>
          <div style={s.contactBox}>
            <div style={s.contactIcon}>⏰</div>
            <div style={s.contactLbl}>Время работы</div>
            <div style={s.contactVal}>Пн–Пт 9:00–18:00</div>
          </div>
        </div>
      </div>
    </div>
  )
}
