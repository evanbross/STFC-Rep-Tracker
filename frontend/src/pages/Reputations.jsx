/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import { useState, useEffect } from 'react';
import { api, errorMessage } from '../api/client';

const COL_ORDER = ['low_limit', 'high_limit', 'messages_count', 'credit_amount'];

const sortedDataKeys = (obj) =>
  Object.keys(obj)
    .filter(k => k !== 'id' && k !== 'name')
    .sort((a, b) => {
      const ai = COL_ORDER.indexOf(a);
      const bi = COL_ORDER.indexOf(b);
      if (ai === -1 && bi === -1) return 0;
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    });

const RepTable = ({ title, tableName, data, onSaved }) => {
  const [editing, setEditing] = useState(false);
  // ai: claude-opus-5-5 | 2026-11-18
  // rows is the edit buffer, copied from data by handleEdit; outside editing
  // the table shows data directly, so a reload after saving needs no sync effect.
  const [rows, setRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const shown = editing ? rows : data;

  const handleEdit = () => {
    setRows(data.map(r => ({ ...r })));
    setError(null);
    setEditing(true);
  };

  const handleCancel = () => {
    setError(null);
    setEditing(false);
  };

  const handleChange = (idx, field, value) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const original = data;
      const promises = rows
        .filter((row, idx) => {
          const orig = original[idx];
          return Object.keys(row).some(k => String(row[k]) !== String(orig[k]));
        })
        // ai: claude-opus-5-5 | 2026-11-18 — id is in the URL; the API rejects unknown body keys
        .map(({id, ...fields}) => api.put(`/api/reputations/by-table/${tableName}/${id}`, fields));

      await Promise.all(promises);
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(errorMessage(e, 'Failed to save tiers.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="container">
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            {shown.length > 0 && sortedDataKeys(shown[0])
              .map(k => <th key={k} className="text-right">{k.replace(/_/g, ' ')}</th>)
            }
          </tr>
        </thead>
        <tbody>
          {shown.length === 0 ? (
            <tr><td colSpan="3">No reputations found.</td></tr>
          ) : shown.map((rep, idx) => (
            <tr key={rep.id ?? idx}>
              <td>
                {editing
                  ? <input
                      type="text"
                      value={rep.name ?? ''}
                      onChange={e => handleChange(idx, 'name', e.target.value)}
                      style={{ width: '100%' }}
                    />
                  : rep.name
                }
              </td>
              {sortedDataKeys(rep)
                .map(k => (
                  <td key={k} className="text-right">
                    {editing
                      ? <input
                          type="number"
                          value={rep[k] ?? ''}
                          onChange={e => handleChange(idx, k, e.target.value === '' ? null : Number(e.target.value))}
                          style={{ width: '10em', textAlign: 'right' }}
                        />
                      : (rep[k] !== null && rep[k] !== undefined ? Number(rep[k]).toLocaleString() : '-')
                    }
                  </td>
                ))
              }
            </tr>
          ))}
        </tbody>
      </table>
      {error && <div style={{ color: 'red', marginTop: '0.5em' }}>{error}</div>}
      <div style={{ marginTop: '0.5em', display: 'flex', gap: '0.5em' }}>
        {!editing
          ? <button onClick={handleEdit}>Edit</button>
          : <>
              <button onClick={handleSave} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              <button onClick={handleCancel} disabled={saving}>Cancel</button>
            </>
        }
      </div>
    </div>
  );
};

const Reputations = () => {
  const [reputationGroups, setReputationGroups] = useState([]);
  const [loading, setLoading] = useState(true);

  // ai: claude-opus-5-5 | 2026-11-18
  // loading starts true and only the first load shows the spinner; a reload
  // after saving keeps the tables on screen.
  const loadAllReputations = () =>
    api.get('/api/reputations/all')
      .then(response => setReputationGroups(response.data))
      .catch(error => console.error('Error loading reputations:', error))
      .finally(() => setLoading(false));

  useEffect(() => {
    loadAllReputations();
  }, []);

  return (
    <div className="reputations-page">
      <h1>Reputation Tiers</h1>

      {loading ? (
        <div>Loading...</div>
      ) : reputationGroups.map((group, idx) => (
        <RepTable
          key={idx}
          title={group.title}
          tableName={group.table_name}
          data={group.data}
          onSaved={loadAllReputations}
        />
      ))}
    </div>
  );
};

export default Reputations;