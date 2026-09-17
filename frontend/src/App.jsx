/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * LICENSE: Personal Use Only
 * This source code is made available for personal, non-commercial use only.
 * You may read, study, and run this code for personal purposes.
 * You may NOT:
 *   - Use this code, in whole or in part, in any commercial product or service
 *   - Sell, sublicense, or otherwise monetize this code or derivatives of it
 *   - Redistribute this code without explicit written permission from ZombieTech LLC
 *
 * No warranty is provided, express or implied. Use at your own risk.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import React, { Suspense, lazy } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Factions = lazy(() => import('./pages/Factions'))
const Reputations = lazy(() => import('./pages/Reputations'))
const SystemTargets = lazy(() => import('./pages/SystemTargets'))
const Combat = lazy(() => import('./pages/Combat'))

function App() {
  return (
    <Router>
      <div>
        <nav>
          <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink>
          <NavLink to="/factions" className={({ isActive }) => isActive ? 'active' : ''}>Factions</NavLink>
          <NavLink to="/reputations" className={({ isActive }) => isActive ? 'active' : ''}>Reputations</NavLink>
          <NavLink to="/system-targets" className={({ isActive }) => isActive ? 'active' : ''}>System Targets</NavLink>
          <NavLink to="/combat" className={({ isActive }) => isActive ? 'active' : ''}>Combat</NavLink>
        </nav>

        <Suspense fallback={<div>Loading...</div>}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/factions" element={<Factions />} />
            <Route path="/reputations" element={<Reputations />} />
            <Route path="/system-targets" element={<SystemTargets />} />
            <Route path="/combat" element={<Combat />} />
          </Routes>
        </Suspense>
      </div>
    </Router>
  )
}

export default App
