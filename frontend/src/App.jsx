import React from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Factions from './pages/Factions'
import Reputations from './pages/Reputations'

function App() {
  return (
    <Router>
      <div>
        <nav>
          <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink>
          <NavLink to="/factions" className={({ isActive }) => isActive ? 'active' : ''}>Factions</NavLink>
          <NavLink to="/reputations" className={({ isActive }) => isActive ? 'active' : ''}>Reputations</NavLink>
        </nav>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/factions" element={<Factions />} />
          <Route path="/reputations" element={<Reputations />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
