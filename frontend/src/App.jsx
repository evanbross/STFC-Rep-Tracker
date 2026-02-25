import React from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Factions from './pages/Factions'
import Reputations from './pages/Reputations'
import ApiPage from './pages/ApiPage'

function App() {
  return (
    <Router>
      <div>
        <nav>
          <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''}>Tracker</NavLink>
          <NavLink to="/factions" className={({ isActive }) => isActive ? 'active' : ''}>Factions</NavLink>
          <NavLink to="/reputations" className={({ isActive }) => isActive ? 'active' : ''}>Reputations</NavLink>
          <NavLink to="/api-docs" className={({ isActive }) => isActive ? 'active' : ''}>API</NavLink>
        </nav>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/factions" element={<Factions />} />
          <Route path="/reputations" element={<Reputations />} />
          <Route path="/api-docs" element={<ApiPage />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
