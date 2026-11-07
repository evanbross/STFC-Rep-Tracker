/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Territory Schedule modal, moved out of Dashboard.jsx. Render it only while
// open: mounting it loads the schedule and, if Google Calendar is connected,
// checks it. Connecting needs the user's click. // ai: claude-opus-5-5 | 2026-11-07
import React from 'react';
import useTerritorySchedule from './useTerritorySchedule';

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const utcTimeToLocal = (utcTimeStr) => {
    if (!utcTimeStr) return '';
    const [hours, minutes] = utcTimeStr.split(':').map(Number);
    const d = new Date();
    d.setUTCHours(hours, minutes, 0, 0);
    return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
};

const TerritoryScheduleModal = ({onClose}) => {
    const {
        scheduleList,
        scheduleForm,
        setScheduleForm,
        editingId,
        calendarAuthenticated,
        availableCalendars,
        calPickerSelectedId,
        setCalPickerSelectedId,
        scheduleStatus,
        connectCalendar,
        runCalendarCheck,
        addToCalendar,
        startEdit,
        cancelEdit,
        saveScheduleEntry,
        deleteScheduleEntry,
    } = useTerritorySchedule();

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
            backgroundColor: 'rgba(0,0,0,0.75)', zIndex: 1000,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
            <div style={{
                backgroundColor: '#1e1e1e', border: '1px solid #444',
                borderRadius: '8px', padding: '1.5rem', width: '520px',
                maxHeight: '80vh', overflowY: 'auto',
            }}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem'}}>
                    <h3 style={{margin: 0}}>Territory Schedule</h3>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', color: '#aaa',
                        fontSize: '1.4rem', cursor: 'pointer', lineHeight: 1,
                    }}>×</button>
                </div>

                {/* Google Calendar connection row */}
                <div style={{
                    display: 'flex', alignItems: 'center', gap: '0.6rem',
                    marginBottom: '1.25rem', padding: '0.5rem 0.75rem',
                    backgroundColor: '#252525', borderRadius: '5px', flexWrap: 'wrap',
                }}>
                    <span style={{fontSize: '0.8rem', color: '#888', whiteSpace: 'nowrap'}}>
                        Google Calendar:
                    </span>
                    {scheduleStatus !== null ? (
                        <span style={{fontSize: '0.8rem', color: '#90CAF9', fontStyle: 'italic'}}>
                            {scheduleStatus}…
                        </span>
                    ) : calendarAuthenticated ? (
                        <>
                            <select
                                value={calPickerSelectedId}
                                onChange={e => setCalPickerSelectedId(e.target.value)}
                                disabled={!availableCalendars}
                                style={{
                                    flex: 1, minWidth: 0,
                                    fontSize: '0.8rem', padding: '0.2rem 0.4rem',
                                    backgroundColor: '#1e1e1e', color: '#eee',
                                    border: '1px solid #555', borderRadius: '3px',
                                }}
                            >
                                {availableCalendars
                                    ? availableCalendars.map(cal => (
                                        <option key={cal.id} value={cal.id}>{cal.summary}</option>
                                    ))
                                    : <option>Loading calendars…</option>
                                }
                            </select>
                            <button
                                onClick={runCalendarCheck}
                                style={{
                                    padding: '0.2rem 0.6rem', fontSize: '0.78rem',
                                    backgroundColor: '#1a73e8', color: 'white',
                                    border: 'none', borderRadius: '3px', cursor: 'pointer',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                Check Calendar
                            </button>
                        </>
                    ) : (
                        // ai: claude-opus-5-5 | 2026-11-07
                        // Google sign-in starts only from this click, never on open (N-B5).
                        <>
                            <span style={{fontSize: '0.8rem', color: '#e57373', flex: 1}}>Not connected</span>
                            <button
                                onClick={connectCalendar}
                                title="Opens Google's sign-in page in your browser"
                                style={{
                                    padding: '0.2rem 0.6rem', fontSize: '0.78rem',
                                    backgroundColor: '#1a73e8', color: 'white',
                                    border: 'none', borderRadius: '3px', cursor: 'pointer',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                Connect Google Calendar
                            </button>
                        </>
                    )}
                </div>

                {/* Add / update form */}
                <p style={{margin: '0 0 0.75rem', fontSize: '0.8rem', color: '#888'}}>
                    Event time should be entered in <strong style={{color: '#aaa'}}>UTC</strong>.
                </p>
                <div style={{display: 'grid', gridTemplateColumns: '1fr auto auto auto auto', gap: '0.5rem', alignItems: 'center', marginBottom: '1.25rem'}}>
                    <div>
                        <input
                            list="territory-system-names"
                            value={scheduleForm.name}
                            onChange={e => setScheduleForm(prev => ({...prev, name: e.target.value}))}
                            placeholder="System name"
                            style={{width: '100%', padding: '0.4rem 0.6rem', backgroundColor: '#2a2a2a', border: '1px solid #555', borderRadius: '4px', color: 'white'}}
                        />
                        <datalist id="territory-system-names">
                            {[...new Set(scheduleList.map(s => s.name))].map(n => <option key={n} value={n}/>)}
                        </datalist>
                    </div>
                    <select
                        value={scheduleForm.day_of_week}
                        onChange={e => setScheduleForm(prev => ({...prev, day_of_week: e.target.value}))}
                        style={{padding: '0.4rem 0.6rem', backgroundColor: '#2a2a2a', border: '1px solid #555', borderRadius: '4px', color: 'white'}}
                    >
                        {DAY_NAMES.map((d, i) => <option key={i} value={i}>{d}</option>)}
                    </select>
                    <input
                        type="time"
                        value={scheduleForm.event_time}
                        onChange={e => setScheduleForm(prev => ({...prev, event_time: e.target.value}))}
                        style={{padding: '0.4rem 0.6rem', backgroundColor: '#2a2a2a', border: '1px solid #555', borderRadius: '4px', color: 'white'}}
                    />
                    <button
                        onClick={saveScheduleEntry}
                        disabled={!scheduleForm.name.trim() || !scheduleForm.event_time}
                        style={{
                            padding: '0.4rem 0.9rem',
                            backgroundColor: editingId !== null ? '#1565C0' : '#00796B',
                            color: 'white', border: 'none', borderRadius: '4px',
                            cursor: 'pointer',
                        }}
                    >
                        {editingId !== null ? 'Update' : 'Save'}
                    </button>
                    {editingId !== null && (
                        <button
                            onClick={cancelEdit}
                            style={{
                                padding: '0.4rem 0.9rem', backgroundColor: 'transparent',
                                color: '#aaa', border: '1px solid #555', borderRadius: '4px',
                                cursor: 'pointer',
                            }}
                        >
                            Cancel
                        </button>
                    )}
                </div>

                {/* Existing entries */}
                {scheduleStatus !== null ? (
                    <div style={{textAlign: 'center', padding: '2rem 0', color: '#888'}}>
                        <div style={{
                            display: 'inline-block',
                            width: '1.5rem', height: '1.5rem',
                            border: '3px solid #444',
                            borderTopColor: '#90CAF9',
                            borderRadius: '50%',
                            animation: 'spin 0.75s linear infinite',
                        }}/>
                        <p style={{margin: '0.5rem 0 0', fontSize: '0.85rem'}}>{scheduleStatus}…</p>
                    </div>
                ) : scheduleList.length === 0 ? (
                    <p style={{color: '#888', fontSize: '0.9rem', textAlign: 'center', margin: '1rem 0'}}>
                        No systems saved yet.
                    </p>
                ) : (
                    <table style={{width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem'}}>
                        <thead>
                            <tr style={{borderBottom: '1px solid #444', color: '#aaa', textAlign: 'left'}}>
                                <th style={{padding: '0.35rem 0.5rem'}}>System</th>
                                <th style={{padding: '0.35rem 0.5rem'}}>Day</th>
                                <th style={{padding: '0.35rem 0.5rem'}}>UTC</th>
                                <th style={{padding: '0.35rem 0.5rem'}}>Local</th>
                                <th style={{padding: '0.35rem 0.5rem'}}>Calendar</th>
                                <th style={{padding: '0.35rem 0.5rem'}}></th>
                            </tr>
                        </thead>
                        <tbody>
                            {scheduleList.map(s => {
                                let calCell;
                                if (!('calendar_event' in s)) {
                                    calCell = <span style={{color: '#555'}}>—</span>;
                                } else if (s.calendar_event === null) {
                                    calCell = <span style={{color: '#888'}} title={s.calendar_error || 'Calendar unavailable'}>—</span>;
                                } else if (s.calendar_event === false) {
                                    calCell = <span style={{color: '#e57373'}} title="No event found on this date">✗</span>;
                                } else {
                                    calCell = <span style={{color: '#81c784'}} title={`${s.calendar_event.summary} @ ${s.calendar_event.start}`}>✓</span>;
                                }
                                return (
                                <tr key={s.id} style={{borderBottom: '1px solid #333'}}>
                                    <td style={{padding: '0.35rem 0.5rem', fontWeight: 'bold'}}>{s.name}</td>
                                    <td style={{padding: '0.35rem 0.5rem', color: '#aaa'}}>{DAY_NAMES[s.day_of_week]}</td>
                                    <td style={{padding: '0.35rem 0.5rem'}}>{s.event_time}</td>
                                    <td style={{padding: '0.35rem 0.5rem', color: '#aaa'}}>{utcTimeToLocal(s.event_time)}</td>
                                    <td style={{padding: '0.35rem 0.5rem'}}>{calCell}</td>
                                    <td style={{padding: '0.35rem 0.5rem', textAlign: 'right', display: 'flex', gap: '0.4rem', justifyContent: 'flex-end'}}>
                                        <button
                                            onClick={() => addToCalendar(s.id)}
                                            disabled={s.calendar_event !== false}
                                            title={
                                                s.calendar_event === false ? 'Create Google Calendar event' :
                                                s.calendar_event ? 'Event already on calendar' :
                                                'Check calendar first'
                                            }
                                            style={{
                                                padding: '0.2rem 0.5rem', fontSize: '0.8rem',
                                                backgroundColor: 'transparent', border: '1px solid #555',
                                                borderRadius: '3px',
                                                color: s.calendar_event === false ? '#81c784' : '#555',
                                                cursor: s.calendar_event === false ? 'pointer' : 'not-allowed',
                                            }}
                                        >
                                            + Cal
                                        </button>
                                        <button
                                            onClick={() => startEdit(s)}
                                            style={{
                                                padding: '0.2rem 0.5rem', fontSize: '0.8rem',
                                                backgroundColor: editingId === s.id ? '#1565C0' : 'transparent',
                                                border: '1px solid #555',
                                                borderRadius: '3px', color: '#90CAF9', cursor: 'pointer',
                                            }}
                                        >
                                            Edit
                                        </button>
                                        <button
                                            onClick={() => deleteScheduleEntry(s.id)}
                                            style={{
                                                padding: '0.2rem 0.5rem', fontSize: '0.8rem',
                                                backgroundColor: 'transparent', border: '1px solid #555',
                                                borderRadius: '3px', color: '#e57373', cursor: 'pointer',
                                            }}
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};

export default TerritoryScheduleModal;
