// Биржа заданий — с геофильтрами: радиус, свой адрес, район / ветка метро
import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  TextInput, RefreshControl, ActivityIndicator,
  ScrollView, LayoutAnimation, Platform, UIManager,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import { getTasks } from '../api/client';

// Анимация раскрытия гео-панели на Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const KARI  = '#A01F72';
const DARK  = '#242D4A';
const GREEN = '#27ae60';

// ──────────────────────────────────────────────────────────────────────────────
// КОНСТАНТЫ ФИЛЬТРОВ
// ──────────────────────────────────────────────────────────────────────────────

// Статус задания
const STATUS_FILTERS = [
  { key: 'available',   label: 'Доступные' },
  { key: 'in_progress', label: 'В работе'  },
  { key: 'done',        label: 'Завершённые' },
];

// Варианты радиуса поиска (null = без ограничений)
const RADIUS_OPTIONS = [
  { key: 1,    label: '1 км'  },
  { key: 3,    label: '3 км'  },
  { key: 5,    label: '5 км'  },
  { key: 10,   label: '10 км' },
  { key: null, label: 'Любое' },
];

// Районы / Станции метро
// Для пилота (Иркутск) — административные районы города.
// В городах с метро (Москва, СПб, Новосибирск) заменить на реальные
// станции с цветами линий: { key: 'arbat', label: 'Арбатская', color: '#0055A5', line: 3 }
const GEO_LANDMARKS = [
  { key: null,   label: 'Все районы',    color: '#888',    icon: '🗺'  },
  { key: 'sver', label: 'Свердловский',  color: '#A01F72', icon: '📍'  },
  { key: 'okt',  label: 'Октябрьский',   color: '#1976D2', icon: '📍'  },
  { key: 'kir',  label: 'Кировский',     color: '#388E3C', icon: '📍'  },
  { key: 'len',  label: 'Ленинский',     color: '#F57C00', icon: '📍'  },
  { key: 'prav', label: 'Правобережный', color: '#7B1FA2', icon: '📍'  },
];

// ──────────────────────────────────────────────────────────────────────────────
// ДЕМО-ДАННЫЕ (с координатами и привязкой к районам)
// partner: true  — задание от внешнего партнёра (не KARI)
//          false — задание KARI (недоступно для тех, кто в стоп-листе)
// ──────────────────────────────────────────────────────────────────────────────
const DEMO_TASKS = [
  {
    id: 'task-001',
    title: 'Уборка торгового зала',
    store: 'ТЦ «Карамель»',
    address: 'г. Иркутск, ул. Байкальская, 253А',
    category: 'Уборка',
    amount: 1500,
    deadline: '2026-04-01',
    status: 'available',
    duration_hours: 3,
    executors_needed: 2,
    executors_taken: 1,
    coords: { lat: 52.2658, lng: 104.3410 },
    district: 'sver',
    partner: false,
  },
  {
    id: 'task-002',
    title: 'Выкладка весенней коллекции',
    store: 'ТЦ «Мегас»',
    address: 'г. Иркутск, ул. Сергеева, 3',
    category: 'Выкладка',
    amount: 2200,
    deadline: '2026-04-02',
    status: 'available',
    duration_hours: 4,
    executors_needed: 3,
    executors_taken: 0,
    coords: { lat: 52.2891, lng: 104.2611 },
    district: 'okt',
    partner: false,
  },
  {
    id: 'task-003',
    title: 'Переоценка товаров',
    store: 'ТЦ «Сильвер Молл»',
    address: 'г. Иркутск, ул. Трактовая, 12',
    category: 'Переоценка',
    amount: 1800,
    deadline: '2026-04-03',
    status: 'available',
    duration_hours: 5,
    executors_needed: 2,
    executors_taken: 2,
    coords: { lat: 52.3012, lng: 104.2356 },
    district: 'sver',
    partner: false,
  },
  {
    id: 'task-004',
    title: 'Инвентаризация склада',
    store: 'ТЦ «Аквамолл»',
    address: 'г. Иркутск, ул. Баумана, 220',
    category: 'Инвентаризация',
    amount: 3500,
    deadline: '2026-04-05',
    status: 'available',
    duration_hours: 8,
    executors_needed: 4,
    executors_taken: 1,
    coords: { lat: 52.2483, lng: 104.2988 },
    district: 'len',
    partner: false,
  },
  {
    id: 'task-005',
    title: 'Промо-акция: раздача листовок',
    store: 'ТЦ «Карамель»',
    address: 'г. Иркутск, ул. Байкальская, 253А',
    category: 'Промо',
    amount: 900,
    deadline: '2026-04-01',
    status: 'in_progress',
    duration_hours: 2,
    executors_needed: 1,
    executors_taken: 1,
    coords: { lat: 52.2658, lng: 104.3410 },
    district: 'sver',
    partner: false,
  },
  {
    id: 'task-006',
    title: 'Сборка торгового оборудования',
    store: 'ТЦ «СМ Сити»',
    address: 'г. Иркутск, ул. Розы Люксембург, 184',
    category: 'Монтаж',
    amount: 4000,
    deadline: '2026-04-07',
    status: 'available',
    duration_hours: 6,
    executors_needed: 3,
    executors_taken: 0,
    coords: { lat: 52.2756, lng: 104.3058 },
    district: 'kir',
    partner: false,
  },
  // ── Задания от партнёров (доступны всем, включая тех, кто в стоп-листе KARI) ──
  {
    id: 'partner-001',
    title: 'Расстановка обуви Ecco',
    store: 'Ecco — ТЦ «Аквамолл»',
    address: 'г. Иркутск, ул. Баумана, 220',
    category: 'Выкладка',
    amount: 1900,
    deadline: '2026-04-03',
    status: 'available',
    duration_hours: 3,
    executors_needed: 2,
    executors_taken: 0,
    coords: { lat: 52.2483, lng: 104.2988 },
    district: 'len',
    partner: true,
    partner_name: 'Ecco',
  },
  {
    id: 'partner-002',
    title: 'Уборка зала после распродажи',
    store: 'Zara — ТЦ «Сильвер Молл»',
    address: 'г. Иркутск, ул. Трактовая, 12',
    category: 'Уборка',
    amount: 1400,
    deadline: '2026-04-04',
    status: 'available',
    duration_hours: 2,
    executors_needed: 3,
    executors_taken: 1,
    coords: { lat: 52.3012, lng: 104.2356 },
    district: 'sver',
    partner: true,
    partner_name: 'Zara',
  },
];

const STATUS_COLOR = { available: KARI, in_progress: GREEN, done: '#888' };
const STATUS_LABEL = { available: 'Доступно', in_progress: 'В работе', done: 'Завершено' };

// ──────────────────────────────────────────────────────────────────────────────
// УТИЛИТЫ
// ──────────────────────────────────────────────────────────────────────────────

// Расстояние по формуле Хаверсина (результат в км)
function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180)
    * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Красивое отображение расстояния
function fmtDist(d) {
  if (d === null || d === undefined) return null;
  if (d < 1) return `${Math.round(d * 1000)} м`;
  return `${d.toFixed(1)} км`;
}

// ──────────────────────────────────────────────────────────────────────────────
// КОМПОНЕНТ
// ──────────────────────────────────────────────────────────────────────────────
export default function TasksScreen({ navigation, route }) {
  // partnerOnly=true приходит из StopListBlockedScreen (стоп-лист KARI)
  // Показываем только задания внешних партнёров — их брать можно всем
  const partnerOnly = route?.params?.partnerOnly ?? false;

  const [tasks, setTasks]       = useState(DEMO_TASKS);
  const [filter, setFilter]     = useState('available');
  const [search, setSearch]     = useState('');
  const [refreshing, setRefresh]= useState(false);
  const [isDemo, setIsDemo]     = useState(true);

  // ── Гео-фильтр ──
  const [showGeoPanel, setShowGeoPanel]   = useState(false);
  const [geoRadius, setGeoRadius]         = useState(null);    // км или null
  const [geoSource, setGeoSource]         = useState('gps');   // 'gps' | 'address'
  const [geoAddress, setGeoAddress]       = useState('');
  const [geoLandmark, setGeoLandmark]     = useState(null);    // ключ района/метро
  const [userCoords, setUserCoords]       = useState(null);    // { lat, lng }
  const [locStatus, setLocStatus]         = useState('idle');  // idle | loading | ok | error
  const [addrLoading, setAddrLoading]     = useState(false);
  const addrTimer = useRef(null);

  const geoActive = geoRadius !== null || geoLandmark !== null;

  // ── Загрузка с API ──
  const loadTasks = async (sf = filter) => {
    try {
      const res = await getTasks({ status: sf, search });
      setTasks(res.data.items || []);
      setIsDemo(false);
    } catch {
      setTasks(DEMO_TASKS.filter(t => t.status === sf));
    }
  };

  useEffect(() => { loadTasks(filter); }, [filter, search]);

  const onRefresh = async () => {
    setRefresh(true);
    await loadTasks(filter);
    setRefresh(false);
  };

  // ── Геолокация по GPS ──
  const requestGpsLocation = async () => {
    setLocStatus('loading');
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') { setLocStatus('error'); return; }
      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setUserCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      setLocStatus('ok');
    } catch {
      setLocStatus('error');
    }
  };

  // Запрашиваем GPS автоматически при открытии панели в режиме GPS
  useEffect(() => {
    if (showGeoPanel && geoSource === 'gps' && !userCoords) {
      requestGpsLocation();
    }
  }, [showGeoPanel, geoSource]);

  // ── Геокодирование адреса ──
  // В реальной реализации → Yandex Geocoding API:
  // GET https://geocode-maps.yandex.ru/1.x/?apikey=KEY&geocode=ADDR&format=json
  const geocodeAddress = (addr) => {
    clearTimeout(addrTimer.current);
    if (!addr.trim()) { setUserCoords(null); setLocStatus('idle'); return; }
    setAddrLoading(true);
    addrTimer.current = setTimeout(() => {
      // Демо: возвращаем центр Иркутска как заглушку
      setUserCoords({ lat: 52.2837, lng: 104.2963 });
      setLocStatus('ok');
      setAddrLoading(false);
    }, 900);
  };

  // ── Открытие / закрытие панели с анимацией ──
  const toggleGeoPanel = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setShowGeoPanel(v => !v);
  };

  // ── Сброс всех гео-фильтров ──
  const resetGeo = () => {
    setGeoRadius(null);
    setGeoLandmark(null);
    setGeoAddress('');
    setUserCoords(null);
    setLocStatus('idle');
  };

  // ── Задачи с рассчитанным расстоянием ──
  const base = isDemo
    ? DEMO_TASKS.filter(t => t.status === filter)
    : tasks;

  const withDist = base.map(t => {
    if (userCoords && t.coords) {
      return { ...t, distance: haversine(userCoords.lat, userCoords.lng, t.coords.lat, t.coords.lng) };
    }
    return { ...t, distance: null };
  });

  // ── Применяем фильтры и сортировку ──
  const displayTasks = withDist
    .filter(t => {
      // Режим «только партнёры»: скрываем задания KARI
      if (partnerOnly && !t.partner) return false;
      if (search && !t.title.toLowerCase().includes(search.toLowerCase()) &&
                    !t.store.toLowerCase().includes(search.toLowerCase())) return false;
      // Радиус — только если есть координаты пользователя
      if (geoRadius !== null && userCoords && t.distance !== null && t.distance > geoRadius) return false;
      // Район / метро
      if (geoLandmark !== null && t.district !== geoLandmark) return false;
      return true;
    })
    .sort((a, b) => {
      // Если есть расстояния — сортируем по близости
      if (a.distance !== null && b.distance !== null) return a.distance - b.distance;
      if (a.distance !== null) return -1;
      if (b.distance !== null) return 1;
      return 0;
    });

  const isFull = (t) => t.executors_taken >= t.executors_needed;

  // ── Метка результата ──
  const activeLandmark = GEO_LANDMARKS.find(l => l.key === geoLandmark);
  const resultsLabel = [
    `${displayTasks.length} заданий`,
    geoRadius !== null ? `в радиусе ${geoRadius} км` : null,
    activeLandmark?.key ? `· ${activeLandmark.label}` : null,
  ].filter(Boolean).join(' ');

  // ────────────────────────────────────────────────────────────────────────────
  // РЕНДЕР КАРТОЧКИ
  // ────────────────────────────────────────────────────────────────────────────
  const renderTask = ({ item: t }) => (
    <TouchableOpacity
      style={[s.card, isFull(t) && t.status === 'available' && s.cardFull]}
      onPress={() => navigation.navigate('TaskDetail', { task: t })}
    >
      <View style={s.cardTop}>
        <View style={s.cardLeft}>
          <Text style={s.cardTitle}>{t.title}</Text>
          <View style={s.tagRow}>
            <View style={[s.tag, { backgroundColor: STATUS_COLOR[t.status] + '18' }]}>
              <Text style={[s.tagText, { color: STATUS_COLOR[t.status] }]}>{STATUS_LABEL[t.status]}</Text>
            </View>
            <View style={s.tag}>
              <Text style={s.tagText}>📂 {t.category}</Text>
            </View>
            {/* Значок расстояния — только если есть геолокация */}
            {t.distance !== null && (
              <View style={s.distTag}>
                <Text style={s.distTagText}>📍 {fmtDist(t.distance)}</Text>
              </View>
            )}
          </View>
        </View>
        <View style={s.amountBox}>
          <Text style={s.amount}>{t.amount.toLocaleString('ru-RU')}</Text>
          <Text style={s.currency}>₽</Text>
        </View>
      </View>

      {/* Значок партнёра */}
      {t.partner && (
        <View style={s.partnerTag}>
          <Text style={s.partnerTagText}>🤝 Партнёр: {t.partner_name}</Text>
        </View>
      )}
      <Text style={s.store}>🏪 {t.store}</Text>
      <Text style={s.addr}>📍 {t.address}</Text>

      <View style={s.details}>
        <Text style={s.detail}>⏱ {t.duration_hours} ч.</Text>
        <Text style={s.detail}>📅 до {t.deadline}</Text>
        <View style={[s.execBadge, isFull(t) && s.execBadgeFull]}>
          <Text style={[s.execText, isFull(t) && s.execTextFull]}>
            {isFull(t) ? '⛔ Все места заняты' : `👥 ${t.executors_taken}/${t.executors_needed}`}
          </Text>
        </View>
      </View>

      {t.status === 'available' && !isFull(t) && (
        <TouchableOpacity
          style={s.takeBtn}
          onPress={() => navigation.navigate('TaskDetail', { task: t })}
        >
          <Text style={s.takeBtnText}>Взять задание →</Text>
        </TouchableOpacity>
      )}
    </TouchableOpacity>
  );

  // ────────────────────────────────────────────────────────────────────────────
  // ГЕО-ПАНЕЛЬ
  // ────────────────────────────────────────────────────────────────────────────
  const GeoPanel = () => (
    <View style={s.geoPanel}>

      {/* ── Радиус ── */}
      <Text style={s.geoSectionLabel}>📏 Радиус поиска</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.chipRow}>
        {RADIUS_OPTIONS.map(opt => (
          <TouchableOpacity
            key={String(opt.key)}
            style={[s.chip, geoRadius === opt.key && s.chipActive]}
            onPress={() => setGeoRadius(opt.key)}
          >
            <Text style={[s.chipText, geoRadius === opt.key && s.chipTextActive]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* ── Источник локации ── */}
      <Text style={[s.geoSectionLabel, { marginTop: 14 }]}>🧭 Откуда считать расстояние</Text>
      <View style={s.sourceRow}>
        <TouchableOpacity
          style={[s.sourceBtn, geoSource === 'gps' && s.sourceBtnActive]}
          onPress={() => { setGeoSource('gps'); if (!userCoords) requestGpsLocation(); }}
        >
          <Text style={[s.sourceBtnText, geoSource === 'gps' && s.sourceBtnTextActive]}>
            {locStatus === 'loading' && geoSource === 'gps' ? '⏳' : '🛰'} Моё место
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.sourceBtn, geoSource === 'address' && s.sourceBtnActive]}
          onPress={() => setGeoSource('address')}
        >
          <Text style={[s.sourceBtnText, geoSource === 'address' && s.sourceBtnTextActive]}>
            🏠 Другой адрес
          </Text>
        </TouchableOpacity>
      </View>

      {/* Строка ввода адреса */}
      {geoSource === 'address' && (
        <View style={s.addrRow}>
          <TextInput
            style={s.addrInput}
            placeholder="Адрес, метро, название места..."
            placeholderTextColor="#bbb"
            value={geoAddress}
            onChangeText={v => { setGeoAddress(v); geocodeAddress(v); }}
          />
          {addrLoading
            ? <ActivityIndicator size="small" color={KARI} style={{ marginLeft: 8 }} />
            : locStatus === 'ok' && geoAddress.length > 0
              ? <Text style={s.addrOk}>✓</Text>
              : null
          }
        </View>
      )}

      {/* Статус GPS */}
      {geoSource === 'gps' && locStatus === 'loading' && (
        <View style={s.geoStatusRow}>
          <ActivityIndicator size="small" color={KARI} />
          <Text style={s.geoStatusText}>Определяем местоположение...</Text>
        </View>
      )}
      {geoSource === 'gps' && locStatus === 'ok' && (
        <Text style={s.geoOk}>✓ Геолокация определена — карта подходящих заданий обновлена</Text>
      )}
      {geoSource === 'gps' && locStatus === 'error' && (
        <Text style={s.geoErr}>⚠️ Нет доступа к геолокации. Разрешите в настройках → Конфиденциальность → Геолокация.</Text>
      )}

      {/* ── Район / Станция метро ── */}
      <Text style={[s.geoSectionLabel, { marginTop: 14 }]}>🏙 Район / Станция метро</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.chipRow}>
        {GEO_LANDMARKS.map(lm => {
          const isActive = geoLandmark === lm.key;
          return (
            <TouchableOpacity
              key={String(lm.key)}
              style={[
                s.chip,
                isActive && { backgroundColor: lm.color, borderColor: lm.color },
              ]}
              onPress={() => setGeoLandmark(lm.key)}
            >
              <Text style={[s.chipText, isActive && { color: '#fff', fontWeight: '700' }]}>
                {lm.icon} {lm.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Подсказка про метро */}
      <Text style={s.geoHint}>
        Для городов с метро (Москва, СПб) — здесь будут станции и ветки
      </Text>

      {/* Кнопка сброса */}
      {geoActive && (
        <TouchableOpacity style={s.resetBtn} onPress={resetGeo}>
          <Text style={s.resetBtnText}>✕  Сбросить гео-фильтры</Text>
        </TouchableOpacity>
      )}
    </View>
  );

  // ────────────────────────────────────────────────────────────────────────────
  // ОСНОВНОЙ РЕНДЕР
  // ────────────────────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={s.safe} edges={['top']}>

      {/* Шапка */}
      <View style={s.header}>
        <Text style={s.headerTitle}>Биржа заданий</Text>
        {isDemo && <Text style={s.demoTag}>🛠 Демо</Text>}
      </View>

      {/* Баннер режима «только партнёры» (показывается когда пришли из стоп-листа) */}
      {partnerOnly && (
        <View style={s.partnerBanner}>
          <Text style={s.partnerBannerText}>
            🤝 Показаны заказы партнёров — их брать могут все исполнители
          </Text>
        </View>
      )}

      {/* Поиск */}
      <View style={s.searchBox}>
        <TextInput
          style={s.searchInput}
          placeholder="🔍 Поиск по названию или магазину..."
          placeholderTextColor="#bbb"
          value={search}
          onChangeText={setSearch}
        />
      </View>

      {/* Строка: статус-фильтры + кнопка гео */}
      <View style={s.filterBar}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={s.filterChips}
        >
          {STATUS_FILTERS.map(f => (
            <TouchableOpacity
              key={f.key}
              style={[s.filterBtn, filter === f.key && s.filterBtnActive]}
              onPress={() => setFilter(f.key)}
            >
              <Text style={[s.filterText, filter === f.key && s.filterTextActive]}>
                {f.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Кнопка «Рядом» / «Фильтр» */}
        <TouchableOpacity
          style={[s.geoBtn, (showGeoPanel || geoActive) && s.geoBtnActive]}
          onPress={toggleGeoPanel}
        >
          <Text style={[s.geoBtnText, (showGeoPanel || geoActive) && s.geoBtnTextActive]}>
            📍 {geoActive ? 'Фильтр ●' : 'Рядом'} {showGeoPanel ? '▲' : '▼'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Гео-панель (раскрывается анимированно) */}
      {showGeoPanel && <GeoPanel />}

      {/* Строка результатов */}
      <View style={s.resultsBar}>
        <Text style={s.resultsCount}>{resultsLabel}</Text>
        {userCoords && (
          <Text style={s.sortHint}>↕ по расстоянию</Text>
        )}
      </View>

      {/* Список заданий */}
      <FlatList
        data={displayTasks}
        keyExtractor={t => t.id}
        renderItem={renderTask}
        contentContainerStyle={s.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={KARI} />
        }
        ListEmptyComponent={
          <View style={s.empty}>
            <Text style={s.emptyIcon}>{geoActive ? '🗺' : '📋'}</Text>
            <Text style={s.emptyText}>
              {geoActive ? 'Нет заданий в этой зоне' : 'Нет доступных заданий'}
            </Text>
            <Text style={s.emptyHint}>
              {geoActive
                ? 'Попробуйте увеличить радиус или выбрать другой район'
                : 'Новые задания появляются каждый день'}
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// СТИЛИ
// ──────────────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f0f2f5' },

  // Шапка
  header: {
    backgroundColor: KARI, paddingHorizontal: 20, paddingVertical: 16,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  headerTitle: { fontSize: 20, fontWeight: '800', color: '#fff' },
  demoTag:     { fontSize: 12, color: 'rgba(255,255,255,0.7)', fontWeight: '600' },

  // Поиск
  searchBox: {
    backgroundColor: '#fff', paddingHorizontal: 16, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: '#f0f0f0',
  },
  searchInput: {
    backgroundColor: '#f5f5f5', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 10,
    fontSize: 14, color: DARK,
  },

  // Строка статус-фильтров
  filterBar: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#f0f0f0',
    paddingRight: 12,
  },
  filterChips:    { paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
  filterBtn:      { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: '#f0f0f0' },
  filterBtnActive:{ backgroundColor: KARI },
  filterText:     { fontSize: 13, fontWeight: '600', color: '#666' },
  filterTextActive:{ color: '#fff' },

  // Кнопка геофильтра
  geoBtn: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20,
    borderWidth: 1.5, borderColor: '#ddd', backgroundColor: '#fff',
    flexShrink: 0,
  },
  geoBtnActive:     { borderColor: KARI, backgroundColor: KARI + '12' },
  geoBtnText:       { fontSize: 13, fontWeight: '700', color: '#888' },
  geoBtnTextActive: { color: KARI },

  // ── ГЕО-ПАНЕЛЬ ──
  geoPanel: {
    backgroundColor: '#fff',
    borderBottomWidth: 1, borderBottomColor: '#eee',
    paddingHorizontal: 16, paddingTop: 14, paddingBottom: 16,
  },
  geoSectionLabel: {
    fontSize: 11, fontWeight: '800', color: '#aaa',
    letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 8,
  },

  // Чипы радиуса и районов
  chipRow:        { marginBottom: 4 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 7,
    borderRadius: 20, borderWidth: 1.5, borderColor: '#e0e0e0',
    backgroundColor: '#fafafa', marginRight: 8,
  },
  chipActive:     { backgroundColor: KARI, borderColor: KARI },
  chipText:       { fontSize: 13, fontWeight: '600', color: '#555' },
  chipTextActive: { color: '#fff', fontWeight: '700' },

  // Источник локации
  sourceRow: { flexDirection: 'row', gap: 10, marginBottom: 8 },
  sourceBtn: {
    flex: 1, paddingVertical: 9, borderRadius: 10,
    borderWidth: 1.5, borderColor: '#e0e0e0', alignItems: 'center',
    backgroundColor: '#fafafa',
  },
  sourceBtnActive:    { borderColor: KARI, backgroundColor: KARI + '10' },
  sourceBtnText:      { fontSize: 13, fontWeight: '600', color: '#666' },
  sourceBtnTextActive:{ color: KARI, fontWeight: '700' },

  // Ввод адреса
  addrRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#f5f5f5', borderRadius: 10,
    paddingHorizontal: 12, marginBottom: 6,
  },
  addrInput: { flex: 1, paddingVertical: 10, fontSize: 13, color: DARK },
  addrOk:    { fontSize: 16, color: GREEN, marginLeft: 6 },

  // Статус GPS
  geoStatusRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  geoStatusText:{ fontSize: 12, color: '#888' },
  geoOk: { fontSize: 12, color: GREEN, fontWeight: '600', marginBottom: 6 },
  geoErr: {
    fontSize: 12, color: '#e53935', lineHeight: 18,
    backgroundColor: '#fff5f5', borderRadius: 8,
    padding: 8, marginBottom: 6,
  },

  // Подсказка
  geoHint: { fontSize: 11, color: '#bbb', marginTop: 6, fontStyle: 'italic' },

  // Кнопка сброса
  resetBtn: {
    marginTop: 12, paddingVertical: 10, borderRadius: 10,
    borderWidth: 1.5, borderColor: '#e53935', alignItems: 'center',
  },
  resetBtnText: { fontSize: 13, fontWeight: '700', color: '#e53935' },

  // Строка результатов
  resultsBar: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 8,
    backgroundColor: '#f0f2f5',
  },
  resultsCount: { fontSize: 12, color: '#888', fontWeight: '600' },
  sortHint:     { fontSize: 11, color: KARI, fontWeight: '700' },

  // Список
  list: { padding: 16, gap: 12 },

  // Карточка задания
  card: {
    backgroundColor: '#fff', borderRadius: 16, padding: 16,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 8, elevation: 3,
  },
  cardFull: { opacity: 0.65 },

  cardTop:   { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  cardLeft:  { flex: 1, marginRight: 12 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: DARK, marginBottom: 6 },

  tagRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  tag: {
    backgroundColor: '#f0f0f0', borderRadius: 6,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  tagText: { fontSize: 11, fontWeight: '600', color: '#555' },

  // Значок расстояния
  distTag: { backgroundColor: '#e8f5e9', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  distTagText: { fontSize: 11, fontWeight: '700', color: '#2e7d32' },

  amountBox: { alignItems: 'flex-end' },
  amount:    { fontSize: 22, fontWeight: '900', color: KARI },
  currency:  { fontSize: 12, color: KARI, fontWeight: '600' },

  store: { fontSize: 13, color: '#555', marginBottom: 2 },
  addr:  { fontSize: 12, color: '#888', marginBottom: 12 },

  details: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12 },
  detail:  {
    fontSize: 12, color: '#666', backgroundColor: '#f5f5f5',
    borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3,
  },

  execBadge:     { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, backgroundColor: '#e8f5e9' },
  execBadgeFull: { backgroundColor: '#ffebee' },
  execText:      { fontSize: 12, fontWeight: '600', color: GREEN },
  execTextFull:  { color: '#e53935' },

  takeBtn: {
    backgroundColor: KARI, borderRadius: 10,
    paddingVertical: 12, alignItems: 'center',
  },
  takeBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },

  // Пустой список
  empty:     { alignItems: 'center', paddingTop: 60 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyText: { fontSize: 16, fontWeight: '600', color: DARK, marginBottom: 6 },
  emptyHint: { fontSize: 13, color: '#888', textAlign: 'center', paddingHorizontal: 32 },

  // Баннер «только партнёры» (стоп-лист режим)
  partnerBanner: {
    backgroundColor: '#e8f5e9', borderBottomWidth: 1, borderBottomColor: '#c8e6c9',
    paddingHorizontal: 16, paddingVertical: 10,
  },
  partnerBannerText: { fontSize: 13, fontWeight: '700', color: '#2e7d32', textAlign: 'center' },

  // Значок партнёра на карточке
  partnerTag: {
    alignSelf: 'flex-start', backgroundColor: '#e3f2fd',
    borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, marginBottom: 4,
  },
  partnerTagText: { fontSize: 11, fontWeight: '700', color: '#1565c0' },
});
