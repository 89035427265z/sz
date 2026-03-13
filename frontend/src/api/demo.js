// =============================================================================
// KARI.Самозанятые — Демо-данные для всех страниц
// =============================================================================
// Используются как fallback когда бэкенд недоступен.
// Данные соответствуют seed.py — Иркутский регион, пилот Апрель 2026.
// =============================================================================

// ---------------------------------------------------------------------------
// Исполнители (UsersPage)
// ---------------------------------------------------------------------------
export const DEMO_USERS = {
  items: [
    { id: '1', full_name: 'Иванов Алексей Николаевич',     phone: '+79992000000', inn: '381300000001', fns_status: 'active',   status: 'active',  income_from_kari_year: 2_180_000, bank_name: 'Сбербанк',    bank_card_masked: '**** **** **** 4821', created_at: '2025-10-15' },
    { id: '2', full_name: 'Петров Андрей Сергеевич',        phone: '+79992000001', inn: '381300000002', fns_status: 'active',   status: 'active',  income_from_kari_year: 1_980_000, bank_name: 'Тинькофф',    bank_card_masked: '**** **** **** 7734', created_at: '2025-11-02' },
    { id: '3', full_name: 'Сидоров Виктор Константинович',  phone: '+79992000002', inn: '381300000003', fns_status: 'inactive', status: 'blocked', income_from_kari_year:   240_000, bank_name: 'ВТБ',         bank_card_masked: '**** **** **** 2290', created_at: '2025-09-18' },
    { id: '4', full_name: 'Кузнецова Мария Павловна',       phone: '+79992000003', inn: '381300000004', fns_status: 'active',   status: 'active',  income_from_kari_year:   785_000, bank_name: 'Альфа-Банк',  bank_card_masked: '**** **** **** 9115', created_at: '2025-12-01' },
    { id: '5', full_name: 'Попов Денис Владимирович',       phone: '+79992000004', inn: '381300000005', fns_status: 'active',   status: 'active',  income_from_kari_year:   430_000, bank_name: 'Сбербанк',    bank_card_masked: '**** **** **** 1144', created_at: '2026-01-10' },
    { id: '6', full_name: 'Волкова Ольга Анатольевна',      phone: '+79992000005', inn: '381300000006', fns_status: 'active',   status: 'active',  income_from_kari_year:   910_500, bank_name: 'Тинькофф',    bank_card_masked: '**** **** **** 5523', created_at: '2025-11-25' },
    { id: '7', full_name: 'Новиков Игорь Борисович',        phone: '+79992000006', inn: '381300000007', fns_status: 'active',   status: 'active',  income_from_kari_year:   330_000, bank_name: 'ВТБ',         bank_card_masked: '**** **** **** 8876', created_at: '2026-01-20' },
    { id: '8', full_name: 'Морозова Светлана Игоревна',     phone: '+79992000007', inn: '381300000008', fns_status: 'active',   status: 'active',  income_from_kari_year: 2_290_000, bank_name: 'Сбербанк',    bank_card_masked: '**** **** **** 3312', created_at: '2025-08-30' },
    { id: '9', full_name: 'Соколов Роман Дмитриевич',       phone: '+79992000008', inn: '381300000009', fns_status: 'active',   status: 'active',  income_from_kari_year:   145_000, bank_name: 'Газпромбанк', bank_card_masked: '**** **** **** 6690', created_at: '2026-02-05' },
    { id: '10', full_name: 'Лебедева Наталья Юрьевна',     phone: '+79992000009', inn: '381300000010', fns_status: 'inactive', status: 'blocked', income_from_kari_year:    95_000, bank_name: 'Тинькофф',    bank_card_masked: '**** **** **** 4417', created_at: '2025-10-08' },
    { id: '11', full_name: 'Козлов Артём Максимович',       phone: '+79992000010', inn: '381300000011', fns_status: 'active',   status: 'active',  income_from_kari_year:   560_000, bank_name: 'Сбербанк',    bank_card_masked: '**** **** **** 7723', created_at: '2026-01-15' },
    { id: '12', full_name: 'Николаева Юлия Алексеевна',     phone: '+79992000011', inn: '381300000012', fns_status: 'active',   status: 'active',  income_from_kari_year:   220_000, bank_name: 'ВТБ',         bank_card_masked: '**** **** **** 9988', created_at: '2026-02-10' },
    { id: '13', full_name: 'Орлов Сергей Михайлович',       phone: '+79992000012', inn: '381300000013', fns_status: 'active',   status: 'active',  income_from_kari_year:   875_000, bank_name: 'Альфа-Банк',  bank_card_masked: '**** **** **** 2234', created_at: '2025-12-18' },
    { id: '14', full_name: 'Захарова Екатерина Вадимовна',  phone: '+79992000013', inn: '381300000014', fns_status: 'active',   status: 'active',  income_from_kari_year:   410_000, bank_name: 'Сбербанк',    bank_card_masked: '**** **** **** 5501', created_at: '2025-11-30' },
    { id: '15', full_name: 'Смирнов Олег Валентинович',     phone: '+79992000014', inn: '381300000015', fns_status: 'blocked',  status: 'blocked', income_from_kari_year:   680_000, bank_name: 'Тинькофф',    bank_card_masked: '**** **** **** 8843', created_at: '2025-09-05' },
    { id: '16', full_name: 'Федорова Ирина Петровна',       phone: '+79992000015', inn: '381300000016', fns_status: 'active',   status: 'active',  income_from_kari_year:   195_000, bank_name: 'ВТБ',         bank_card_masked: '**** **** **** 1167', created_at: '2026-01-28' },
    { id: '17', full_name: 'Малинин Андрей Игоревич',       phone: '+79992000016', inn: '381300000017', fns_status: 'active',   status: 'active',  income_from_kari_year:   730_000, bank_name: 'Сбербанк',    bank_card_masked: '**** **** **** 4490', created_at: '2025-10-22' },
    { id: '18', full_name: 'Борисова Анна Николаевна',      phone: '+79992000017', inn: '381300000018', fns_status: 'active',   status: 'active',  income_from_kari_year:   290_000, bank_name: 'Газпромбанк', bank_card_masked: '**** **** **** 7756', created_at: '2026-02-01' },
    { id: '19', full_name: 'Громов Владимир Олегович',      phone: '+79992000018', inn: '381300000019', fns_status: 'active',   status: 'active',  income_from_kari_year: 1_120_000, bank_name: 'Тинькофф',    bank_card_masked: '**** **** **** 3301', created_at: '2025-09-12' },
    { id: '20', full_name: 'Тихонова Ксения Борисовна',     phone: '+79992000019', inn: '381300000020', fns_status: 'active',   status: 'active',  income_from_kari_year:   480_000, bank_name: 'Сбербанк',    bank_card_masked: '**** **** **** 6678', created_at: '2025-12-25' },
  ],
  total: 30,
}

// ---------------------------------------------------------------------------
// Задания (TasksPage)
// ---------------------------------------------------------------------------
export const DEMO_TASKS = {
  items: [
    { id: 't01', title: 'Уборка торгового зала',              category: 'cleaning',      status: 'in_progress',    amount: 1800, store_name: 'KARI ТЦ Сибирь',         executor_name: 'Иванов А.Н.',      deadline: '2026-03-06', created_at: '2026-03-04' },
    { id: 't02', title: 'Выкладка весенней коллекции',        category: 'merchandising', status: 'published',      amount: 3200, store_name: 'KARI ТЦ Карамель',        executor_name: null,               deadline: '2026-03-07', created_at: '2026-03-04' },
    { id: 't03', title: 'Инвентаризация (женский зал)',        category: 'inventory',     status: 'submitted',      amount: 4500, store_name: 'KARI ТЦ Мегас',           executor_name: 'Волкова О.А.',     deadline: '2026-03-05', created_at: '2026-03-03' },
    { id: 't04', title: 'Разгрузка товара (42 коробки)',       category: 'unloading',     status: 'completed',      amount: 2800, store_name: 'KARI ТЦ Альтаир',         executor_name: 'Петров А.С.',      deadline: '2026-03-03', created_at: '2026-03-01' },
    { id: 't05', title: 'Промо-акция «Весна 2026»',           category: 'promotion',     status: 'taken',          amount: 2000, store_name: 'KARI ТЦ Фортуна',         executor_name: 'Козлов А.М.',      deadline: '2026-03-08', created_at: '2026-03-04' },
    { id: 't06', title: 'Перемаркировка обуви (новые цены)',   category: 'marking',       status: 'accepted',       amount: 1600, store_name: 'KARI ТЦ Версаль',         executor_name: 'Орлов С.М.',       deadline: '2026-03-05', created_at: '2026-03-03' },
    { id: 't07', title: 'Мерчандайзинг детской зоны',         category: 'merchandising', status: 'completed',      amount: 3800, store_name: 'KARI ул. Ленина',          executor_name: 'Кузнецова М.П.',   deadline: '2026-03-02', created_at: '2026-02-28' },
    { id: 't08', title: 'Генеральная уборка склада',           category: 'cleaning',      status: 'published',      amount: 2200, store_name: 'KARI ТЦ Радуга',          executor_name: null,               deadline: '2026-03-09', created_at: '2026-03-04' },
    { id: 't09', title: 'Инвентаризация мужской коллекции',   category: 'inventory',     status: 'completed',      amount: 5500, store_name: 'KARI ТЦ Сибирь',         executor_name: 'Громов В.О.',      deadline: '2026-02-28', created_at: '2026-02-25' },
    { id: 't10', title: 'Расстановка оборудования',            category: 'other',         status: 'rejected',       amount: 1500, store_name: 'KARI ТЦ Карамель',        executor_name: 'Новиков И.Б.',     deadline: '2026-03-04', created_at: '2026-03-02' },
    { id: 't11', title: 'Приёмка новой коллекции',             category: 'unloading',     status: 'in_progress',    amount: 3200, store_name: 'KARI ТЦ Ручей',           executor_name: 'Малинин А.И.',     deadline: '2026-03-06', created_at: '2026-03-04' },
    { id: 't12', title: 'Оформление сезонной витрины',         category: 'merchandising', status: 'published',      amount: 4000, store_name: 'KARI ТЦ Модный квартал',  executor_name: null,               deadline: '2026-03-10', created_at: '2026-03-04' },
    { id: 't13', title: 'Консультирование покупателей',         category: 'promotion',     status: 'completed',      amount: 2400, store_name: 'KARI ТЦ Мегас',           executor_name: 'Захарова Е.В.',    deadline: '2026-03-01', created_at: '2026-02-28' },
    { id: 't14', title: 'Нанесение ценников на коллекцию',    category: 'marking',       status: 'submitted',      amount: 1200, store_name: 'KARI ТЦ Альтаир',         executor_name: 'Борисова А.Н.',    deadline: '2026-03-05', created_at: '2026-03-03' },
    { id: 't15', title: 'Уборка примерочных и входной зоны',  category: 'cleaning',      status: 'completed',      amount: 1400, store_name: 'KARI ТЦ Версаль',         executor_name: 'Тихонова К.Б.',    deadline: '2026-02-27', created_at: '2026-02-26' },
    { id: 't16', title: 'Полная инвентаризация склада',        category: 'inventory',     status: 'draft',          amount: 6000, store_name: 'KARI ул. Ленина',          executor_name: null,               deadline: '2026-03-12', created_at: '2026-03-04' },
    { id: 't17', title: 'Разгрузка и сортировка обуви',        category: 'unloading',     status: 'completed',      amount: 3400, store_name: 'KARI ТЦ Фортуна',         executor_name: 'Соколов Р.Д.',     deadline: '2026-02-26', created_at: '2026-02-24' },
    { id: 't18', title: 'Промо у входа в ТЦ',                 category: 'promotion',     status: 'taken',          amount: 1800, store_name: 'KARI ТЦ Радуга',          executor_name: 'Федорова И.П.',    deadline: '2026-03-07', created_at: '2026-03-04' },
    { id: 't19', title: 'Выкладка коллекции детской обуви',   category: 'merchandising', status: 'in_progress',    amount: 2800, store_name: 'KARI ТЦ Ручей',           executor_name: 'Николаева Ю.А.',   deadline: '2026-03-06', created_at: '2026-03-04' },
    { id: 't20', title: 'Маркировка склада (новые зоны)',      category: 'marking',       status: 'completed',      amount: 1800, store_name: 'KARI ТЦ Сибирь',         executor_name: 'Лебедева Н.Ю.',    deadline: '2026-02-25', created_at: '2026-02-23' },
  ],
  total: 85,
}

// ---------------------------------------------------------------------------
// Выплаты (PaymentsPage)
// ---------------------------------------------------------------------------
export const DEMO_PAYMENTS = {
  items: [
    { id: 'p01', executor_name: 'Волкова О.А.',      task_title: 'Инвентаризация (женский зал)',       amount: 4500, tax_amount: 270,  status: 'processing', created_at: '2026-03-03', paid_at: null,         sovcombank_ref: null              },
    { id: 'p02', executor_name: 'Орлов С.М.',        task_title: 'Перемаркировка обуви',               amount: 1600, tax_amount: 96,   status: 'processing', created_at: '2026-03-03', paid_at: null,         sovcombank_ref: null              },
    { id: 'p03', executor_name: 'Петров А.С.',       task_title: 'Разгрузка товара (42 коробки)',      amount: 2800, tax_amount: 168,  status: 'paid',       created_at: '2026-03-01', paid_at: '2026-03-03', sovcombank_ref: 'SCB-A4F91C2E10' },
    { id: 'p04', executor_name: 'Кузнецова М.П.',    task_title: 'Мерчандайзинг детской зоны',         amount: 3800, tax_amount: 228,  status: 'paid',       created_at: '2026-02-28', paid_at: '2026-03-01', sovcombank_ref: 'SCB-B7D22A1F55' },
    { id: 'p05', executor_name: 'Громов В.О.',       task_title: 'Инвентаризация мужской коллекции',   amount: 5500, tax_amount: 330,  status: 'paid',       created_at: '2026-02-25', paid_at: '2026-02-27', sovcombank_ref: 'SCB-C3E44B9D81' },
    { id: 'p06', executor_name: 'Захарова Е.В.',     task_title: 'Консультирование покупателей',        amount: 2400, tax_amount: 144,  status: 'paid',       created_at: '2026-02-28', paid_at: '2026-03-01', sovcombank_ref: 'SCB-D9F55C0E22' },
    { id: 'p07', executor_name: 'Тихонова К.Б.',     task_title: 'Уборка примерочных',                 amount: 1400, tax_amount: 84,   status: 'paid',       created_at: '2026-02-26', paid_at: '2026-02-28', sovcombank_ref: 'SCB-E1A66D1F33' },
    { id: 'p08', executor_name: 'Соколов Р.Д.',      task_title: 'Разгрузка и сортировка обуви',       amount: 3400, tax_amount: 204,  status: 'paid',       created_at: '2026-02-24', paid_at: '2026-02-26', sovcombank_ref: 'SCB-F2B77E2A44' },
    { id: 'p09', executor_name: 'Малинин А.И.',      task_title: 'Маркировка склада',                  amount: 1800, tax_amount: 108,  status: 'paid',       created_at: '2026-02-23', paid_at: '2026-02-25', sovcombank_ref: 'SCB-G3C88F3B55' },
    { id: 'p10', executor_name: 'Иванов А.Н.',       task_title: 'Выкладка ассортимента (зима 2025)',  amount: 3000, tax_amount: 180,  status: 'failed',     created_at: '2026-02-20', paid_at: null,         sovcombank_ref: null              },
    { id: 'p11', executor_name: 'Попов Д.В.',        task_title: 'Уборка торгового зала',              amount: 1800, tax_amount: 108,  status: 'paid',       created_at: '2026-02-22', paid_at: '2026-02-24', sovcombank_ref: 'SCB-H4D99A4C66' },
    { id: 'p12', executor_name: 'Николаева Ю.А.',    task_title: 'Промо-акция перед закрытием',        amount: 2200, tax_amount: 132,  status: 'paid',       created_at: '2026-02-18', paid_at: '2026-02-20', sovcombank_ref: 'SCB-I5EAA5D77' },
  ],
  total: 48,
}

export const DEMO_REGISTRIES = {
  items: [
    { id: 'r01', name: 'Реестр выплат март 2026',   status: 'completed',  total_amount: 184_000, total_rows: 32, processed_rows: 32, created_at: '2026-03-01', completed_at: '2026-03-03' },
    { id: 'r02', name: 'Реестр выплат февраль 2026', status: 'completed',  total_amount: 217_500, total_rows: 41, processed_rows: 41, created_at: '2026-02-01', completed_at: '2026-02-04' },
    { id: 'r03', name: 'Реестр тест — Иркутск Запад',status: 'processing', total_amount: 48_000,  total_rows: 9,  processed_rows: 4,  created_at: '2026-03-04', completed_at: null         },
  ],
  total: 3,
}

// ---------------------------------------------------------------------------
// Чеки ФНС (FnsPage)
// ---------------------------------------------------------------------------
export const DEMO_RECEIPTS = {
  items: [
    { id: 'f01', receipt_number: 'ФНС-2026-00030', executor_name: 'Орлов С.М.',        amount: 1600, status: 'issued',     issued_at: '2026-03-04', cancelled_at: null,          task_title: 'Перемаркировка обуви'          },
    { id: 'f02', receipt_number: 'ФНС-2026-00029', executor_name: 'Волкова О.А.',      amount: 4500, status: 'pending',    issued_at: null,          cancelled_at: null,          task_title: 'Инвентаризация (женский зал)'  },
    { id: 'f03', receipt_number: 'ФНС-2026-00028', executor_name: 'Петров А.С.',       amount: 2800, status: 'issued',     issued_at: '2026-03-03', cancelled_at: null,          task_title: 'Разгрузка товара'              },
    { id: 'f04', receipt_number: 'ФНС-2026-00027', executor_name: 'Кузнецова М.П.',    amount: 3800, status: 'issued',     issued_at: '2026-03-01', cancelled_at: null,          task_title: 'Мерчандайзинг детской зоны'   },
    { id: 'f05', receipt_number: 'ФНС-2026-00001', executor_name: 'Иванов А.Н.',       amount: 2400, status: 'cancelled',  issued_at: '2026-02-14', cancelled_at: '2026-02-17',  task_title: 'Уборка торгового зала (фев)'   },
    { id: 'f06', receipt_number: 'ФНС-2026-00026', executor_name: 'Громов В.О.',       amount: 5500, status: 'issued',     issued_at: '2026-02-27', cancelled_at: null,          task_title: 'Инвентаризация мужской коллекции' },
    { id: 'f07', receipt_number: 'ФНС-2026-00025', executor_name: 'Захарова Е.В.',     amount: 2400, status: 'issued',     issued_at: '2026-03-01', cancelled_at: null,          task_title: 'Консультирование покупателей'  },
    { id: 'f08', receipt_number: 'ФНС-2026-00024', executor_name: 'Тихонова К.Б.',     amount: 1400, status: 'issued',     issued_at: '2026-02-28', cancelled_at: null,          task_title: 'Уборка примерочных'            },
    { id: 'f09', receipt_number: 'ФНС-2026-00023', executor_name: 'Соколов Р.Д.',      amount: 3400, status: 'issued',     issued_at: '2026-02-26', cancelled_at: null,          task_title: 'Разгрузка и сортировка'        },
    { id: 'f10', receipt_number: 'ФНС-2026-00022', executor_name: 'Малинин А.И.',      amount: 1800, status: 'issued',     issued_at: '2026-02-25', cancelled_at: null,          task_title: 'Маркировка склада'             },
    { id: 'f11', receipt_number: 'ФНС-2026-00010', executor_name: 'Попов Д.В.',        amount: 1800, status: 'issued',     issued_at: '2026-02-24', cancelled_at: null,          task_title: 'Уборка торгового зала'         },
    { id: 'f12', receipt_number: 'ФНС-2026-00009', executor_name: 'Николаева Ю.А.',    amount: 2200, status: 'issued',     issued_at: '2026-02-20', cancelled_at: null,          task_title: 'Промо-акция'                   },
    { id: 'f13', receipt_number: 'ФНС-2026-00008', executor_name: 'Борисова А.Н.',     amount: 1200, status: 'failed',     issued_at: null,          cancelled_at: null,          task_title: 'Нанесение ценников'            },
  ],
  total: 30,
}
