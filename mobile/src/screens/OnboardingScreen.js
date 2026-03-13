// Онбординг: новый исполнитель заполняет ФИО (3 поля) и ИНН
import React, { useState, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { updateProfile, checkFnsStatus } from '../api/client';
import { useAuth } from '../hooks/useAuth';

const KARI  = '#A01F72';
const DARK  = '#242D4A';

export default function OnboardingScreen({ navigation }) {
  const { user, refreshUser } = useAuth();

  const [step, setStep]         = useState(1);

  // Три отдельных поля для ФИО
  const [lastName,   setLastName]   = useState('');  // Фамилия
  const [firstName,  setFirstName]  = useState('');  // Имя
  const [patronymic, setPatronymic] = useState('');  // Отчество

  const [inn, setInn]               = useState('');
  const [loading, setLoading]       = useState(false);

  // Рефы для перехода между полями по «Далее» на клавиатуре
  const firstNameRef  = useRef(null);
  const patronymicRef = useRef(null);
  const innRef        = useRef(null);

  // Шаг 1 → сохранить ФИО
  const handleStep1 = async () => {
    if (!lastName.trim()) {
      Alert.alert('Ошибка', 'Введите фамилию');
      return;
    }
    if (!firstName.trim()) {
      Alert.alert('Ошибка', 'Введите имя');
      return;
    }
    // Отчество необязательно — некоторые имена его не имеют
    const fullName = [lastName.trim(), firstName.trim(), patronymic.trim()]
      .filter(Boolean)
      .join(' ');

    setLoading(true);
    try {
      await updateProfile({ full_name: fullName });
      setStep(2);
    } catch (e) {
      Alert.alert('Ошибка', e?.response?.data?.detail || 'Не удалось сохранить данные');
    } finally {
      setLoading(false);
    }
  };

  // Шаг 2 → проверить ИНН в ФНС и сохранить
  const handleStep2 = async () => {
    if (inn.replace(/\D/g, '').length !== 12) {
      Alert.alert('Ошибка', 'ИНН самозанятого состоит из 12 цифр');
      return;
    }
    setLoading(true);
    try {
      const res = await checkFnsStatus(inn);
      const fnsStatus = res.data.status; // 'active' | 'inactive'
      if (fnsStatus === 'active') {
        await updateProfile({ inn });
        setStep(3);
      } else {
        Alert.alert(
          'Статус не подтверждён',
          'По данным ФНС вы не являетесь плательщиком НПД.\n\nЗарегистрируйтесь как самозанятый в приложении «Мой налог» и попробуйте снова.',
          [{ text: 'Понятно' }]
        );
      }
    } catch {
      Alert.alert('Ошибка', 'Не удалось проверить статус в ФНС. Попробуйте позже.');
    } finally {
      setLoading(false);
    }
  };

  // Прогресс-бар сверху (3 шага)
  const ProgressBar = () => (
    <View style={s.progressRow}>
      {[1, 2, 3].map((n) => (
        <View key={n} style={[s.progressDot, step >= n && s.progressDotActive]} />
      ))}
    </View>
  );

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">

          {/* Шапка */}
          <View style={s.header}>
            <Text style={s.logoText}>KARI</Text>
            <Text style={s.logoSub}>Регистрация</Text>
          </View>

          <ProgressBar />

          {/* ── Шаг 1 — ФИО (три отдельных поля) ── */}
          {step === 1 && (
            <View style={s.card}>
              <Text style={s.stepNum}>Шаг 1 из 2</Text>
              <Text style={s.title}>Как вас зовут?</Text>
              <Text style={s.subtitle}>
                Введите ФИО как в паспорте — оно будет указано в договоре
              </Text>

              {/* Фамилия */}
              <Text style={s.label}>Фамилия</Text>
              <TextInput
                style={s.input}
                placeholder="Иванов"
                placeholderTextColor="#bbb"
                value={lastName}
                onChangeText={setLastName}
                autoCapitalize="words"
                returnKeyType="next"
                onSubmitEditing={() => firstNameRef.current?.focus()}
              />

              {/* Имя */}
              <Text style={s.label}>Имя</Text>
              <TextInput
                ref={firstNameRef}
                style={s.input}
                placeholder="Иван"
                placeholderTextColor="#bbb"
                value={firstName}
                onChangeText={setFirstName}
                autoCapitalize="words"
                returnKeyType="next"
                onSubmitEditing={() => patronymicRef.current?.focus()}
              />

              {/* Отчество */}
              <Text style={s.label}>
                Отчество{' '}
                <Text style={s.optional}>(необязательно)</Text>
              </Text>
              <TextInput
                ref={patronymicRef}
                style={s.input}
                placeholder="Иванович"
                placeholderTextColor="#bbb"
                value={patronymic}
                onChangeText={setPatronymic}
                autoCapitalize="words"
                returnKeyType="done"
                onSubmitEditing={handleStep1}
              />

              <TouchableOpacity
                style={[s.btn, loading && s.btnOff]}
                onPress={handleStep1}
                disabled={loading}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={s.btnText}>Далее →</Text>
                }
              </TouchableOpacity>
            </View>
          )}

          {/* ── Шаг 2 — ИНН и проверка ФНС ── */}
          {step === 2 && (
            <View style={s.card}>
              <Text style={s.stepNum}>Шаг 2 из 2</Text>
              <Text style={s.title}>Ваш ИНН</Text>
              <Text style={s.subtitle}>
                Введите 12-значный ИНН. Мы проверим ваш статус в «Мой налог» автоматически.
              </Text>

              <Text style={s.label}>ИНН (12 цифр)</Text>
              <TextInput
                ref={innRef}
                style={s.input}
                placeholder="381234567890"
                placeholderTextColor="#bbb"
                keyboardType="number-pad"
                value={inn}
                onChangeText={(t) => setInn(t.replace(/\D/g, '').slice(0, 12))}
                maxLength={12}
              />

              <View style={s.tipBox}>
                <Text style={s.tipText}>
                  💡 ИНН найдёте в приложении «Мой налог» → Профиль
                </Text>
              </View>

              <TouchableOpacity
                style={[s.btn, loading && s.btnOff]}
                onPress={handleStep2}
                disabled={loading}
              >
                {loading
                  ? <><ActivityIndicator color="#fff" /><Text style={s.btnText}>  Проверяем в ФНС…</Text></>
                  : <Text style={s.btnText}>Проверить и продолжить →</Text>
                }
              </TouchableOpacity>

              <TouchableOpacity style={s.backBtn} onPress={() => setStep(1)}>
                <Text style={s.backText}>← Назад</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* ── Шаг 3 — успех ── */}
          {step === 3 && (
            <View style={s.card}>
              <View style={s.successIcon}>
                <Text style={{ fontSize: 48 }}>✅</Text>
              </View>
              <Text style={s.title}>Всё готово!</Text>
              <Text style={s.subtitle}>
                Вы зарегистрированы как самозанятый партнёр KARI.{'\n\n'}
                Теперь можете брать задания, получать выплаты и подписывать документы.
              </Text>

              <View style={s.nextBox}>
                <Text style={s.nextItem}>📋 Биржа заданий — выбирайте задания в ближайших магазинах</Text>
                <Text style={s.nextItem}>💰 Выплаты — в течение 3 дней после подписания акта</Text>
                <Text style={s.nextItem}>📄 Договор — подпишите ПЭП через SMS прямо в приложении</Text>
              </View>

              <TouchableOpacity
                style={s.btn}
                onPress={async () => {
                  // Обновляем user в контексте (теперь inn заполнен)
                  // AppNavigator сам переключится на Main — не нужно navigate вручную
                  await refreshUser();
                }}
              >
                <Text style={s.btnText}>Начать работать →</Text>
              </TouchableOpacity>
            </View>
          )}

        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:   { flex: 1, backgroundColor: KARI },
  flex:   { flex: 1 },
  scroll: { flexGrow: 1, padding: 24, paddingTop: 16 },

  header:  { alignItems: 'center', marginBottom: 20 },
  logoText:{ fontSize: 32, fontWeight: '900', color: '#fff', letterSpacing: 5 },
  logoSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', letterSpacing: 3, marginTop: 2 },

  progressRow: { flexDirection: 'row', justifyContent: 'center', gap: 10, marginBottom: 24 },
  progressDot: { width: 36, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.3)' },
  progressDotActive: { backgroundColor: '#fff' },

  card: {
    backgroundColor: '#fff', borderRadius: 20,
    padding: 28, shadowColor: '#000',
    shadowOpacity: 0.15, shadowRadius: 16, elevation: 8,
  },

  stepNum:  { fontSize: 12, color: KARI, fontWeight: '700', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 },
  title:    { fontSize: 22, fontWeight: '800', color: DARK, marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#666', lineHeight: 20, marginBottom: 24 },

  label:    { fontSize: 13, fontWeight: '600', color: DARK, marginBottom: 6 },
  optional: { fontSize: 12, fontWeight: '400', color: '#999' },
  input: {
    borderWidth: 1.5, borderColor: '#e0e0e0', borderRadius: 12,
    padding: 14, fontSize: 16, color: DARK, marginBottom: 16, backgroundColor: '#fafafa',
  },

  tipBox: {
    backgroundColor: '#fff8f0', borderRadius: 10, padding: 12, marginBottom: 20,
    borderLeftWidth: 3, borderLeftColor: '#f39c12',
  },
  tipText: { fontSize: 13, color: '#666' },

  btn: {
    backgroundColor: KARI, borderRadius: 12,
    paddingVertical: 16, alignItems: 'center',
    flexDirection: 'row', justifyContent: 'center',
  },
  btnOff:  { opacity: 0.6 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700', marginLeft: 4 },

  backBtn: { marginTop: 12, alignItems: 'center', padding: 8 },
  backText: { fontSize: 14, color: KARI, fontWeight: '600' },

  successIcon: { alignItems: 'center', marginBottom: 16 },
  nextBox: { backgroundColor: '#f8f9fa', borderRadius: 12, padding: 16, marginBottom: 24, gap: 10 },
  nextItem: { fontSize: 13, color: DARK, lineHeight: 20 },
});
