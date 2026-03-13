// Экран авторизации: ввод телефона → получение SMS → ввод кода
import React, { useState, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { requestSmsCode } from '../api/client';
import { useAuth } from '../hooks/useAuth';

const KARI = '#A01F72';
const DARK  = '#242D4A';

export default function AuthScreen({ navigation }) {
  const { login } = useAuth();

  // Шаг 1 — ввод телефона, шаг 2 — ввод SMS-кода
  const [step, setStep]       = useState(1);
  const [phone, setPhone]     = useState('');
  const [code, setCode]       = useState('');
  const [loading, setLoading] = useState(false);
  const [timer, setTimer]     = useState(0); // обратный отсчёт для повторной отправки

  const codeRef = useRef(null);

  // Форматируем телефон: +7 (914) 123-45-67
  const formatPhone = (raw) => {
    const digits = raw.replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 1) return digits;
    let res = '+7';
    if (digits.length > 1)  res += ' (' + digits.slice(1, 4);
    if (digits.length >= 4) res += ') ' + digits.slice(4, 7);
    if (digits.length >= 7) res += '-' + digits.slice(7, 9);
    if (digits.length >= 9) res += '-' + digits.slice(9, 11);
    return res;
  };

  // Запросить SMS-код
  const handleSendCode = async () => {
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 11) {
      Alert.alert('Ошибка', 'Введите полный номер телефона');
      return;
    }
    setLoading(true);
    try {
      const res = await requestSmsCode('+' + digits);
      setStep(2);

      // DEV-режим: бэкенд возвращает debug_code — вставляем автоматически
      if (res?.data?.debug_code) {
        setCode(res.data.debug_code);
      }

      // Запускаем таймер 60 секунд для кнопки "Отправить снова"
      setTimer(60);
      const interval = setInterval(() => {
        setTimer(t => {
          if (t <= 1) { clearInterval(interval); return 0; }
          return t - 1;
        });
      }, 1000);
      setTimeout(() => codeRef.current?.focus(), 300);
    } catch (e) {
      Alert.alert('Ошибка', e?.response?.data?.detail || 'Не удалось отправить SMS. Проверьте номер.');
    } finally {
      setLoading(false);
    }
  };

  // Подтвердить код из SMS
  const handleConfirmCode = async () => {
    if (code.length < 6) {
      Alert.alert('Ошибка', 'Введите код из SMS (6 цифр)');
      return;
    }
    setLoading(true);
    try {
      const digits = phone.replace(/\D/g, '');
      const userData = await login('+' + digits, code);
      // Если ИНН не заполнен — отправляем на онбординг
      if (!userData?.inn) {
        navigation.replace('Onboarding');
      }
      // Иначе навигатор сам переведёт на Main (через useAuth)
    } catch (e) {
      Alert.alert('Неверный код', 'Проверьте код из SMS и попробуйте снова');
      setCode('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView
        style={s.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">

          {/* Логотип */}
          <View style={s.logoBox}>
            <Text style={s.logoText}>KARI</Text>
            <Text style={s.logoSub}>САМОЗАНЯТЫЕ</Text>
          </View>

          {/* Карточка */}
          <View style={s.card}>
            {step === 1 ? (
              <>
                <Text style={s.title}>Вход в приложение</Text>
                <Text style={s.subtitle}>
                  Введите номер телефона — пришлём SMS с кодом подтверждения
                </Text>

                <Text style={s.label}>Номер телефона</Text>
                <TextInput
                  style={s.input}
                  placeholder="+7 (___) ___-__-__"
                  placeholderTextColor="#bbb"
                  keyboardType="phone-pad"
                  value={phone}
                  onChangeText={(t) => setPhone(formatPhone(t))}
                  returnKeyType="done"
                  onSubmitEditing={handleSendCode}
                  maxLength={18}
                />

                <TouchableOpacity
                  style={[s.btn, loading && s.btnDisabled]}
                  onPress={handleSendCode}
                  disabled={loading}
                >
                  {loading
                    ? <ActivityIndicator color="#fff" />
                    : <Text style={s.btnText}>Получить код →</Text>
                  }
                </TouchableOpacity>
              </>
            ) : (
              <>
                <Text style={s.title}>Введите код из SMS</Text>
                <Text style={s.subtitle}>
                  Мы отправили 6-значный код на{'\n'}
                  <Text style={s.phoneHighlight}>{phone}</Text>
                </Text>

                <Text style={s.label}>Код подтверждения</Text>
                <TextInput
                  ref={codeRef}
                  style={[s.input, s.inputCode]}
                  placeholder="• • • • • •"
                  placeholderTextColor="#bbb"
                  keyboardType="number-pad"
                  value={code}
                  onChangeText={setCode}
                  maxLength={6}
                  returnKeyType="done"
                  onSubmitEditing={handleConfirmCode}
                />

                <TouchableOpacity
                  style={[s.btn, loading && s.btnDisabled]}
                  onPress={handleConfirmCode}
                  disabled={loading}
                >
                  {loading
                    ? <ActivityIndicator color="#fff" />
                    : <Text style={s.btnText}>Войти →</Text>
                  }
                </TouchableOpacity>

                {/* Отправить снова / таймер */}
                <TouchableOpacity
                  style={[s.resendBtn, timer > 0 && s.resendDisabled]}
                  onPress={timer === 0 ? () => { setStep(1); setCode(''); } : null}
                >
                  <Text style={[s.resendText, timer > 0 && s.resendTextDisabled]}>
                    {timer > 0 ? `Отправить снова через ${timer} сек` : '← Изменить номер телефона'}
                  </Text>
                </TouchableOpacity>
              </>
            )}
          </View>

          {/* Подсказка */}
          <Text style={s.hint}>
            Нажимая «Получить код», вы соглашаетесь{'\n'}
            с условиями работы с KARI как самозанятый
          </Text>

        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: KARI },
  flex:    { flex: 1 },
  scroll:  { flexGrow: 1, justifyContent: 'center', padding: 24 },

  logoBox: { alignItems: 'center', marginBottom: 32 },
  logoText:{ fontSize: 42, fontWeight: '900', color: '#fff', letterSpacing: 6 },
  logoSub: { fontSize: 13, fontWeight: '600', color: 'rgba(255,255,255,0.7)', letterSpacing: 4, marginTop: 2 },

  card: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 28,
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 8,
  },

  title:    { fontSize: 22, fontWeight: '800', color: DARK, marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#666', lineHeight: 20, marginBottom: 24 },
  phoneHighlight: { fontWeight: '700', color: KARI },

  label: { fontSize: 13, fontWeight: '600', color: DARK, marginBottom: 6 },
  input: {
    borderWidth: 1.5,
    borderColor: '#e0e0e0',
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: DARK,
    marginBottom: 20,
    backgroundColor: '#fafafa',
  },
  inputCode: {
    fontSize: 28,
    textAlign: 'center',
    letterSpacing: 12,
    fontWeight: '700',
  },

  btn: {
    backgroundColor: KARI,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  btnDisabled: { opacity: 0.6 },
  btnText:  { color: '#fff', fontSize: 16, fontWeight: '700' },

  resendBtn: { marginTop: 16, alignItems: 'center', padding: 8 },
  resendDisabled: {},
  resendText: { fontSize: 13, color: KARI, fontWeight: '600' },
  resendTextDisabled: { color: '#bbb' },

  hint: {
    textAlign: 'center',
    fontSize: 11,
    color: 'rgba(255,255,255,0.6)',
    marginTop: 24,
    lineHeight: 18,
  },
});
