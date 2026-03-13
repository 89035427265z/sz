// =============================================================================
// KARI.Самозанятые — Общий каркас кабинета (sidebar + контент)
// =============================================================================
// Один Layout для всех ролей. Меню меняется в зависимости от роли пользователя.
// Роли: regional_director, division_director, store_director, hrd

import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.js'
import KariLogo from './KariLogo.jsx'

// Меню по ролям
const NAV_BY_ROLE = {
  regional_director: [
    { to: '/dashboard',               icon: '📊', label: 'Обзор',         end: true },
    { to: '/dashboard/users',         icon: '👥', label: 'Исполнители'               },
    { to: '/dashboard/tasks',         icon: '📋', label: 'Задания'                   },
    { to: '/dashboard/payments',      icon: '💰', label: 'Выплаты'                   },
    { to: '/dashboard/fns',           icon: '🏛️', label: 'ФНС / Чеки'               },
    { to: '/dashboard/analytics',     icon: '📈', label: 'Аналитика'                 },  // v2
    { to: '/dashboard/stop-list',     icon: '🚫', label: 'Стоп-лист'                 },
    { to: '/dashboard/instructions',  icon: '📖', label: 'Инструкции'                },
  ],
  division_director: [
    { to: '/division',                icon: '📊', label: 'Обзор',         end: true },
    { to: '/division/tasks',          icon: '📋', label: 'Задания'                   },
    { to: '/division/budget',         icon: '💼', label: 'Бюджет'                    },
    { to: '/division/users',          icon: '👥', label: 'Исполнители'               },
    { to: '/division/analytics',      icon: '📈', label: 'Аналитика'                 },  // v2
    { to: '/division/instructions',   icon: '📖', label: 'Инструкции'                },
  ],
  store_director: [
    { to: '/store',                   icon: '🏪', label: 'Мой магазин',   end: true },
    { to: '/store/tasks',             icon: '📋', label: 'Задания'                   },
    { to: '/store/accept',            icon: '✅', label: 'Приёмка работ'             },
    { to: '/store/users',             icon: '👥', label: 'Исполнители'               },
    { to: '/store/ratings',           icon: '⭐', label: 'Рейтинги'                  },  // v2
    { to: '/store/instructions',      icon: '📖', label: 'Инструкции'                },
  ],
  hrd: [
    { to: '/hrd',                     icon: '👥', label: 'Исполнители',   end: true },
    { to: '/hrd/documents',           icon: '📄', label: 'Договоры'                  },
    { to: '/hrd/payments',            icon: '💰', label: 'Выплаты'                   },
    { to: '/hrd/fns',                 icon: '🏛️', label: 'ФНС / Чеки'               },
    { to: '/hrd/analytics',           icon: '📈', label: 'Аналитика'                 },
    { to: '/hrd/stop-list',           icon: '🚫', label: 'Стоп-лист'                 },
    { to: '/hrd/instructions',        icon: '📖', label: 'Инструкции'                },
  ],
}

const ROLE_LABELS = {
  regional_director: 'Директор региона',
  division_director: 'Директор подразделения',
  store_director:    'Директор магазина',
  hrd:               'HRD / Бухгалтерия',
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/login') }

  const role        = user?.role || 'regional_director'
  const navItems    = NAV_BY_ROLE[role] || NAV_BY_ROLE.regional_director
  const avatarLetter = user?.full_name?.trim()?.[0]?.toUpperCase() || 'Д'

  return (
    <div style={s.root}>

      {/* ===== Боковое меню ===== */}
      <aside style={s.sidebar}>
        <div style={s.sidebarTop}>
          <KariLogo height={30} color="#fff" />
          <span style={s.sidebarSub}>Самозанятые</span>
        </div>

        <nav style={s.nav}>
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={({ isActive }) => ({
              display:'flex', alignItems:'center', gap:'10px', padding:'10px 12px',
              borderRadius:'8px', textDecoration:'none', fontSize:'14px', fontWeight:'600',
              transition:'all .15s',
              borderLeftWidth:'3px', borderLeftStyle:'solid',
              color:            isActive ? '#fff'                    : 'rgba(255,255,255,.6)',
              background:       isActive ? 'rgba(169,29,122,.25)'    : 'transparent',
              borderLeftColor:  isActive ? '#a91d7a'                 : 'transparent',
            })}
            >
              <span style={s.navIcon}>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div style={s.sidebarFooter}>
          <div style={s.userInfo}>
            <div style={s.avatar}>{avatarLetter}</div>
            <div style={s.userDetails}>
              <div style={s.userName}>{user?.full_name || 'Пользователь'}</div>
              <div style={s.userRole}>{ROLE_LABELS[role] || 'Кабинет'}</div>
            </div>
          </div>
          <button onClick={handleLogout} style={s.btnLogout}>Выйти →</button>
        </div>
      </aside>

      {/* ===== Контент ===== */}
      <main style={s.main}><Outlet /></main>

    </div>
  )
}

const s = {
  root:        { display:'flex', minHeight:'100vh', background:'#f0f2f5', fontFamily:'Nunito,sans-serif' },
  sidebar:     { width:'240px', minWidth:'240px', background:'linear-gradient(180deg,#242D4A 0%,#1a2038 100%)', display:'flex', flexDirection:'column', position:'sticky', top:0, height:'100vh', overflowY:'auto' },
  sidebarTop:  { padding:'24px 20px 20px', borderBottom:'1px solid rgba(255,255,255,.1)', display:'flex', flexDirection:'column', gap:'6px' },
  sidebarSub:  { fontSize:'9px', fontWeight:'800', letterSpacing:'3px', textTransform:'uppercase', color:'#a91d7a', marginLeft:'2px' },
  nav:         { flex:1, padding:'16px 12px', display:'flex', flexDirection:'column', gap:'4px' },
  navItem:     { display:'flex', alignItems:'center', gap:'10px', padding:'10px 12px', borderRadius:'8px', color:'rgba(255,255,255,.6)', textDecoration:'none', fontSize:'14px', fontWeight:'600', transition:'all .15s', borderLeftWidth:'3px', borderLeftStyle:'solid', borderLeftColor:'transparent' },
  navActive:   { background:'rgba(169,29,122,.25)', color:'#fff', borderLeftColor:'#a91d7a' },
  navIcon:     { fontSize:'16px', width:'20px', textAlign:'center', flexShrink:0 },
  sidebarFooter:{ padding:'16px', borderTop:'1px solid rgba(255,255,255,.1)', display:'flex', flexDirection:'column', gap:'12px' },
  userInfo:    { display:'flex', alignItems:'center', gap:'10px' },
  avatar:      { width:'36px', height:'36px', borderRadius:'50%', background:'#a91d7a', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'15px', fontWeight:'800', flexShrink:0 },
  userDetails: { overflow:'hidden' },
  userName:    { fontSize:'13px', fontWeight:'700', color:'#fff', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' },
  userRole:    { fontSize:'11px', color:'rgba(255,255,255,.45)', marginTop:'2px' },
  btnLogout:   { background:'rgba(255,255,255,.08)', border:'1px solid rgba(255,255,255,.15)', color:'rgba(255,255,255,.65)', borderRadius:'6px', padding:'7px 12px', fontSize:'12px', fontWeight:'700', fontFamily:'inherit', cursor:'pointer', width:'100%', textAlign:'center' },
  main:        { flex:1, overflow:'auto', padding:'28px 32px' },
}
