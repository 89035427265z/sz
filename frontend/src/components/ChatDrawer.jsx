// =============================================================================
// KARI.Самозанятые v2 — Компонент чата внутри задания
// Файл: frontend/src/components/ChatDrawer.jsx
// =============================================================================
//
// Выдвижная панель (drawer) с чатом для конкретного задания.
//
// Используется на страницах:
//   - StoreDirectorPage — директор пишет исполнителю
//   - TasksPage (кабинет HRD) — просмотр переписки по заданию
//
// Props:
//   taskId     — ID задания (обязательный)
//   currentUser — объект пользователя { id, full_name, role }
//   receiverId  — ID собеседника
//   receiverName — Имя собеседника (для заголовка)
//   isOpen     — boolean, показать/скрыть
//   onClose    — callback при закрытии
//
// Поведение:
//   - Загружает историю при открытии
//   - Автоскролл к последнему сообщению
//   - Отмечает все как прочитанные при открытии
//   - Реальный API: GET/POST /api/v1/chat/{taskId}/messages
//
// =============================================================================

import { useState, useEffect, useRef, useCallback } from "react";

// Цвета бренда KARI
const KARI_PINK = "#A01F72";
const KARI_DARK = "#242D4A";

// Имитация API (в production — реальные запросы)
const API_BASE = "/api/v1";

async function loadMessages(taskId) {
  // TODO: заменить на реальный fetch
  await new Promise((r) => setTimeout(r, 300));
  const now = new Date();
  return [
    {
      id: "1",
      sender_id: "executor-1",
      receiver_id: "director-1",
      message: "Здравствуйте! Уточните пожалуйста, нужно ли убирать подсобное помещение или только торговый зал?",
      is_read: true,
      photo_url: null,
      created_at: new Date(now.getTime() - 3600000).toISOString(),
    },
    {
      id: "2",
      sender_id: "director-1",
      receiver_id: "executor-1",
      message: "Добрый день! Только торговый зал. Подсобку не трогайте.",
      is_read: true,
      photo_url: null,
      created_at: new Date(now.getTime() - 3500000).toISOString(),
    },
    {
      id: "3",
      sender_id: "executor-1",
      receiver_id: "director-1",
      message: "Понял, приступаю!",
      is_read: true,
      photo_url: null,
      created_at: new Date(now.getTime() - 3400000).toISOString(),
    },
  ];
}

async function sendMessage(taskId, receiverId, message, photoUrl = null) {
  // TODO: заменить на реальный POST /api/v1/chat/{taskId}/messages
  await new Promise((r) => setTimeout(r, 200));
  return {
    id: Date.now().toString(),
    sender_id: "current-user",
    receiver_id: receiverId,
    message,
    is_read: false,
    photo_url: photoUrl,
    created_at: new Date().toISOString(),
  };
}

// =============================================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// =============================================================================

function formatTime(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function formatDate(isoString) {
  const d = new Date(isoString);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (d.toDateString() === today.toDateString()) return "Сегодня";
  if (d.toDateString() === yesterday.toDateString()) return "Вчера";
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}

// Группировка сообщений по датам
function groupMessagesByDate(messages) {
  const groups = {};
  messages.forEach((msg) => {
    const dateKey = new Date(msg.created_at).toDateString();
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(msg);
  });
  return Object.entries(groups).map(([_, msgs]) => ({
    dateLabel: formatDate(msgs[0].created_at),
    messages: msgs,
  }));
}

// =============================================================================
// ГЛАВНЫЙ КОМПОНЕНТ
// =============================================================================

export default function ChatDrawer({
  taskId,
  currentUser,
  receiverId,
  receiverName = "Собеседник",
  isOpen,
  onClose,
}) {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Загрузка сообщений при открытии
  useEffect(() => {
    if (!isOpen || !taskId) return;

    setLoading(true);
    setError(null);
    loadMessages(taskId)
      .then((msgs) => setMessages(msgs))
      .catch((e) => setError("Не удалось загрузить чат"))
      .finally(() => setLoading(false));

    // Фокус на поле ввода
    setTimeout(() => inputRef.current?.focus(), 100);
  }, [isOpen, taskId]);

  // Автоскролл к последнему сообщению
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Отправка сообщения
  const handleSend = useCallback(async () => {
    const text = newMessage.trim();
    if (!text || sending) return;

    setSending(true);
    setNewMessage("");

    try {
      const msg = await sendMessage(taskId, receiverId, text);
      // Добавляем с правильным sender_id
      setMessages((prev) => [...prev, { ...msg, sender_id: currentUser?.id || "current-user" }]);
    } catch (e) {
      setError("Не удалось отправить сообщение");
      setNewMessage(text); // Возвращаем текст в поле
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }, [newMessage, sending, taskId, receiverId, currentUser]);

  // Enter — отправить, Shift+Enter — перенос строки
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const grouped = groupMessagesByDate(messages);
  const currentUserId = currentUser?.id || "current-user";

  // ---- РЕНДЕР ----
  return (
    <>
      {/* Оверлей */}
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.3)",
            zIndex: 999,
          }}
        />
      )}

      {/* Панель чата */}
      <div style={{
        position: "fixed",
        right: 0,
        top: 0,
        bottom: 0,
        width: 400,
        background: "white",
        boxShadow: "-4px 0 20px rgba(0,0,0,0.15)",
        zIndex: 1000,
        display: "flex",
        flexDirection: "column",
        transform: isOpen ? "translateX(0)" : "translateX(100%)",
        transition: "transform 0.3s ease",
        fontFamily: "Nunito, sans-serif",
      }}>

        {/* --- Заголовок --- */}
        <div style={{
          background: KARI_DARK,
          color: "white",
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "white",
              fontSize: 20,
              cursor: "pointer",
              padding: "2px 6px",
              borderRadius: 4,
              lineHeight: 1,
            }}
          >
            ✕
          </button>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>💬 Чат по заданию</div>
            <div style={{ fontSize: 12, color: "#a0aec0" }}>{receiverName}</div>
          </div>
          <div style={{
            background: KARI_PINK,
            borderRadius: 20,
            padding: "2px 10px",
            fontSize: 12,
          }}>
            {messages.length} сообщ.
          </div>
        </div>

        {/* --- Сообщения --- */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          background: "#f8fafc",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}>
          {loading && (
            <div style={{ textAlign: "center", color: "#999", padding: 40 }}>
              ⏳ Загрузка переписки...
            </div>
          )}

          {!loading && messages.length === 0 && (
            <div style={{
              textAlign: "center",
              color: "#999",
              padding: 40,
              fontSize: 14,
            }}>
              💬 Переписка пока пуста.<br />
              <span style={{ fontSize: 12 }}>Начните диалог с исполнителем</span>
            </div>
          )}

          {/* Сообщения сгруппированные по дате */}
          {grouped.map((group) => (
            <div key={group.dateLabel}>
              {/* Разделитель даты */}
              <div style={{
                textAlign: "center",
                color: "#9ca3af",
                fontSize: 12,
                margin: "12px 0 8px",
              }}>
                ─── {group.dateLabel} ───
              </div>

              {/* Сообщения группы */}
              {group.messages.map((msg) => {
                const isMe = msg.sender_id === currentUserId;
                return (
                  <div
                    key={msg.id}
                    style={{
                      display: "flex",
                      justifyContent: isMe ? "flex-end" : "flex-start",
                      marginBottom: 8,
                    }}
                  >
                    <div style={{
                      maxWidth: "75%",
                      background: isMe ? KARI_PINK : "white",
                      color: isMe ? "white" : KARI_DARK,
                      borderRadius: isMe
                        ? "16px 16px 4px 16px"
                        : "16px 16px 16px 4px",
                      padding: "10px 14px",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                      fontSize: 14,
                      lineHeight: 1.5,
                    }}>
                      {/* Фото (если есть) */}
                      {msg.photo_url && (
                        <img
                          src={msg.photo_url}
                          alt="прикреплено"
                          style={{
                            width: "100%",
                            borderRadius: 8,
                            marginBottom: 8,
                            maxHeight: 200,
                            objectFit: "cover",
                          }}
                        />
                      )}
                      {/* Текст */}
                      <div style={{ wordBreak: "break-word" }}>{msg.message}</div>
                      {/* Время + статус прочтения */}
                      <div style={{
                        fontSize: 11,
                        marginTop: 4,
                        textAlign: "right",
                        color: isMe ? "rgba(255,255,255,0.7)" : "#9ca3af",
                      }}>
                        {formatTime(msg.created_at)}
                        {isMe && (
                          <span style={{ marginLeft: 4 }}>
                            {msg.is_read ? "✓✓" : "✓"}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}

          {/* Якорь автоскролла */}
          <div ref={bottomRef} />
        </div>

        {/* --- Ошибка --- */}
        {error && (
          <div style={{
            background: "#fef2f2",
            color: "#dc2626",
            padding: "8px 16px",
            fontSize: 13,
            borderTop: "1px solid #fecaca",
          }}>
            ⚠️ {error}
          </div>
        )}

        {/* --- Поле ввода --- */}
        <div style={{
          padding: "12px 16px",
          background: "white",
          borderTop: "1px solid #e5e7eb",
          display: "flex",
          gap: 10,
          alignItems: "flex-end",
        }}>
          <textarea
            ref={inputRef}
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Сообщение... (Enter — отправить)"
            rows={1}
            style={{
              flex: 1,
              padding: "10px 14px",
              border: "1.5px solid #e5e7eb",
              borderRadius: 12,
              fontSize: 14,
              fontFamily: "Nunito, sans-serif",
              resize: "none",
              outline: "none",
              lineHeight: 1.5,
              maxHeight: 100,
              overflowY: "auto",
              transition: "border-color 0.2s",
            }}
            onFocus={(e) => { e.target.style.borderColor = KARI_PINK; }}
            onBlur={(e) => { e.target.style.borderColor = "#e5e7eb"; }}
          />
          <button
            onClick={handleSend}
            disabled={!newMessage.trim() || sending}
            style={{
              background: newMessage.trim() ? KARI_PINK : "#e5e7eb",
              color: newMessage.trim() ? "white" : "#9ca3af",
              border: "none",
              borderRadius: 12,
              padding: "10px 16px",
              cursor: newMessage.trim() ? "pointer" : "default",
              fontSize: 18,
              transition: "background 0.2s",
              lineHeight: 1,
            }}
          >
            {sending ? "⏳" : "➤"}
          </button>
        </div>

        {/* Подсказка */}
        <div style={{
          textAlign: "center",
          fontSize: 11,
          color: "#9ca3af",
          padding: "4px 0 8px",
          background: "white",
        }}>
          Shift+Enter — перенос строки
        </div>
      </div>
    </>
  );
}

// =============================================================================
// КНОПКА-ТРИГГЕР (добавляется в карточку задания)
// =============================================================================

export function ChatButton({ unreadCount = 0, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        position: "relative",
        background: "transparent",
        border: `1.5px solid ${KARI_PINK}`,
        color: KARI_PINK,
        borderRadius: 8,
        padding: "6px 14px",
        cursor: "pointer",
        fontSize: 14,
        fontWeight: 600,
        fontFamily: "Nunito, sans-serif",
        display: "flex",
        alignItems: "center",
        gap: 6,
        transition: "all 0.2s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = KARI_PINK;
        e.currentTarget.style.color = "white";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = KARI_PINK;
      }}
    >
      💬 Чат
      {unreadCount > 0 && (
        <span style={{
          background: "#dc2626",
          color: "white",
          borderRadius: "50%",
          width: 18,
          height: 18,
          fontSize: 11,
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginLeft: 2,
        }}>
          {unreadCount > 9 ? "9+" : unreadCount}
        </span>
      )}
    </button>
  );
}
