/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// State and API calls behind the Territory Schedule modal, moved out of Dashboard.jsx.
import {useEffect, useRef, useState} from 'react';
import {api, errorMessage, INTERACTIVE_AUTH_TIMEOUT_MS} from '../../api/client';

const EMPTY_FORM = {name: '', day_of_week: 0, event_time: ''};

/**
 * Everything the modal shows and does. Call it from a component that mounts
 * only while the modal is open: mounting loads the schedule and, when Google
 * Calendar is already connected, checks each row against it. Connecting is
 * left to connectCalendar, which only an explicit user click should call (N-B5).
 */
const useTerritorySchedule = () => {
    const [scheduleList, setScheduleList] = useState([]);
    const [scheduleForm, setScheduleForm] = useState(EMPTY_FORM);
    const [editingId, setEditingId] = useState(null);
    const [calendarAuthenticated, setCalendarAuthenticated] = useState(null);
    const [availableCalendars, setAvailableCalendars] = useState(null);
    const [calPickerSelectedId, setCalPickerSelectedId] = useState('primary');
    const [scheduleStatus, setScheduleStatus] = useState(null); // null = idle, string = current step label
    // Opening POSTs check-calendar (Google API calls); StrictMode must not run it twice.
    const openedRef = useRef(false); // ai: claude-opus-5-5 | 2026-11-07

    const checkCalendar = async () => {
        const res = await api.post('/api/territory/systems/check-calendar');
        setScheduleList(res.data);
    };

    const loadCalendars = async () => {
        const res = await api.get('/api/territory/calendars');
        setAvailableCalendars(res.data);
        if (res.data.length > 0) setCalPickerSelectedId(res.data[0].id);
    };

    // ai: claude-opus-5-5 | 2026-11-07
    // Starts Google's consent flow, so only the Connect button calls it (N-B5).
    // The auth response already carries every row checked against the calendar.
    const connectCalendar = async () => {
        setScheduleStatus('Waiting for Google sign-in');
        try {
            const res = await api.post('/api/calendar/auth', null, {timeout: INTERACTIVE_AUTH_TIMEOUT_MS});
            setCalendarAuthenticated(true);
            if (res.data.systems) setScheduleList(res.data.systems);
            setScheduleStatus('Loading calendars');
            await loadCalendars();
        } catch (error) {
            alert(`Google Calendar connection failed:\n\n${errorMessage(error)}`);
        } finally {
            setScheduleStatus(null);
        }
    };

    useEffect(() => {
        if (openedRef.current) return;
        openedRef.current = true;

        const open = async () => {
            try {
                setScheduleStatus('Loading TC times');
                const listRes = await api.get('/api/territory/systems');
                setScheduleList(listRes.data);

                // Asked on every open, so a token that expired since page load is noticed.
                const statusRes = await api.get('/api/calendar/status');
                const isAuth = statusRes.data.authenticated;
                setCalendarAuthenticated(isAuth);
                // ai: claude-opus-5-5 | 2026-11-07
                // Not connected: show the schedule and the Connect button; never start OAuth here (N-B5).
                if (!isAuth) return;

                setScheduleStatus('Scanning calendar');
                await Promise.all([loadCalendars(), checkCalendar()]);
            } catch (error) {
                console.error('Error opening territory schedule:', error);
                alert(`Could not load the territory schedule: ${errorMessage(error)}`);
            } finally {
                setScheduleStatus(null);
            }
        };
        open();
    }, []);

    const runCalendarCheck = async () => {
        try {
            await checkCalendar();
        } catch (error) {
            alert(`Calendar check failed: ${errorMessage(error)}`);
        }
    };

    const addToCalendar = async (id) => {
        try {
            const res = await api.post(
                `/api/territory/systems/${id}/calendar-event`,
                {calendar_id: calPickerSelectedId},
            );
            setScheduleList(prev => prev.map(s => s.id === id ? res.data : s));
        } catch (error) {
            console.error('Error adding calendar event:', error);
            alert(`Failed to add calendar event: ${errorMessage(error)}`);
        }
    };

    const cancelEdit = () => {
        setScheduleForm(EMPTY_FORM);
        setEditingId(null);
    };

    const startEdit = (entry) => {
        setScheduleForm({name: entry.name, day_of_week: entry.day_of_week, event_time: entry.event_time});
        setEditingId(entry.id);
    };

    const saveScheduleEntry = async () => {
        const {name, day_of_week, event_time} = scheduleForm;
        if (!name.trim() || !event_time) return;
        const body = {name: name.trim(), day_of_week: parseInt(day_of_week, 10), event_time};
        try {
            if (editingId !== null) {
                const res = await api.put(`/api/territory/systems/${editingId}`, body);
                setScheduleList(prev => prev.map(s => s.id === editingId ? res.data : s));
                setEditingId(null);
            } else {
                const res = await api.post('/api/territory/systems', body);
                const saved = res.data;
                // Upsert: replace an existing entry with the same name, or append
                setScheduleList(prev => {
                    const idx = prev.findIndex(s => s.name === saved.name);
                    return idx >= 0 ? prev.map(s => s.name === saved.name ? saved : s) : [...prev, saved];
                });
            }
            setScheduleForm(EMPTY_FORM);
            // The save returns at DB speed; calendar status follows without blocking (N-P5).
            if (calendarAuthenticated) {
                checkCalendar().catch(error => console.error('Error checking calendar:', error));
            }
        } catch (error) {
            console.error('Error saving schedule entry:', error);
            alert(`Failed to save schedule entry: ${errorMessage(error)}`);
        }
    };

    const deleteScheduleEntry = async (id) => {
        try {
            await api.delete(`/api/territory/systems/${id}`);
            if (editingId === id) cancelEdit();
            // Keep the other rows' calendar status
            setScheduleList(prev => prev.filter(s => s.id !== id));
        } catch (error) {
            console.error('Error deleting schedule entry:', error);
            alert(`Failed to delete schedule entry: ${errorMessage(error)}`);
        }
    };

    return {
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
    };
};

export default useTerritorySchedule;
