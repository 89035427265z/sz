// =============================================================================
// KARI.Самозанятые — Роутинг приложения
// =============================================================================
// После входа пользователь попадает в свой кабинет в зависимости от роли:
//   regional_director → /dashboard  (кабинет директора региона)
//   division_director → /division   (кабинет директора подразделения)
//   store_director    → /store      (кабинет директора магазина)
//   hrd               → /hrd        (кабинет HRD / бухгалтерии)

import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth.js'

import LoginPage             from './pages/LoginPage.jsx'
import Layout                from './components/Layout.jsx'

// Кабинет директора региона
import DashboardPage         from './pages/DashboardPage.jsx'
import UsersPage             from './pages/UsersPage.jsx'
import TasksPage             from './pages/TasksPage.jsx'
import PaymentsPage          from './pages/PaymentsPage.jsx'
import FnsPage               from './pages/FnsPage.jsx'

// Кабинет директора подразделения
import DivisionDirectorPage  from './pages/DivisionDirectorPage.jsx'

// Кабинет директора магазина
import StoreDirectorPage     from './pages/StoreDirectorPage.jsx'

// Кабинет HRD / Бухгалтерии
import HrdPage               from './pages/HrdPage.jsx'

// Стоп-лист (HRD + директор региона)
import StopListPage          from './pages/StopListPage.jsx'

// Раздел инструкций (общий для всех ролей)
import InstructionsPage      from './pages/InstructionsPage.jsx'

// Новые страницы v2 — объединённый проект
import AnalyticsPage         from './pages/AnalyticsPage.jsx'

// Куда редиректить после логина — зависит от роли
function homeByRole(role) {
  if (role === 'division_director') return '/division'
  if (role === 'store_director')    return '/store'
  if (role === 'hrd')               return '/hrd'
  return '/dashboard'
}

// Обёртка: перенаправляет незалогиненных на /login
function Protected({ children }) {
  const { isLoggedIn } = useAuth()
  return isLoggedIn ? children : <Navigate to="/login" replace />
}

export default function App() {
  const { isLoggedIn, user } = useAuth()
  const home = homeByRole(user?.role)

  return (
    <Routes>

      {/* ── Вход ── */}
      <Route
        path="/login"
        element={isLoggedIn ? <Navigate to={home} replace /> : <LoginPage />}
      />

      {/* ── Кабинет директора региона ── */}
      <Route path="/dashboard" element={<Protected><Layout /></Protected>}>
        <Route index                  element={<DashboardPage />} />
        <Route path="users"           element={<UsersPage />} />
        <Route path="tasks"           element={<TasksPage />} />
        <Route path="payments"        element={<PaymentsPage />} />
        <Route path="fns"             element={<FnsPage />} />
        <Route path="analytics"       element={<AnalyticsPage />} />
        <Route path="instructions"    element={<InstructionsPage />} />
      </Route>

      {/* ── Кабинет директора подразделения ── */}
      <Route path="/division" element={<Protected><Layout /></Protected>}>
        <Route index                  element={<DivisionDirectorPage />} />
        <Route path="tasks"           element={<TasksPage />} />
        <Route path="budget"          element={<DivisionDirectorPage />} />
        <Route path="users"           element={<UsersPage />} />
        <Route path="analytics"       element={<AnalyticsPage />} />
        <Route path="instructions"    element={<InstructionsPage />} />
      </Route>

      {/* ── Кабинет директора магазина ── */}
      <Route path="/store" element={<Protected><Layout /></Protected>}>
        <Route index                  element={<StoreDirectorPage />} />
        <Route path="tasks"           element={<StoreDirectorPage />} />
        <Route path="accept"          element={<StoreDirectorPage />} />
        <Route path="users"           element={<UsersPage />} />
        <Route path="instructions"    element={<InstructionsPage />} />
      </Route>

      {/* ── Кабинет HRD / Бухгалтерии ── */}
      <Route path="/hrd" element={<Protected><Layout /></Protected>}>
        <Route index                  element={<HrdPage />} />
        <Route path="documents"       element={<HrdPage />} />
        <Route path="payments"        element={<HrdPage />} />
        <Route path="fns"             element={<HrdPage />} />
        <Route path="analytics"       element={<AnalyticsPage />} />
        <Route path="stop-list"       element={<StopListPage />} />
        <Route path="instructions"    element={<InstructionsPage />} />
      </Route>

      {/* Стоп-лист также доступен из кабинета директора региона */}
      <Route path="/dashboard/stop-list" element={<Protected><Layout /></Protected>}>
        <Route index element={<StopListPage />} />
      </Route>

      {/* ── Любой неизвестный адрес ── */}
      <Route
        path="*"
        element={<Navigate to={isLoggedIn ? home : '/login'} replace />}
      />

    </Routes>
  )
}
