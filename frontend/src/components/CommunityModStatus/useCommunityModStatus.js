/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-19
// When the community mod last synced to the app.
//
// /status is the source of truth: it's read on mount and again after the event
// stream reconnects, since events sent while disconnected aren't replayed.
// Between those, each `capture` event carries the new time, so a sync shows up
// as it happens without polling.
import {useEffect, useState} from 'react';
import {api, errorMessage} from '../../api/client';

export const STATUS_URL = '/api/community-mod/status';
export const EVENTS_URL = '/api/community-mod/events';

export default function useCommunityModStatus() {
    const [lastReceivedAt, setLastReceivedAt] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;
        let reconnecting = false;

        const loadStatus = async () => {
            try {
                const {data} = await api.get(STATUS_URL);
                if (cancelled) return;
                setLastReceivedAt(data.last_received_at);
                setError(null);
            } catch (err) {
                if (!cancelled) setError(errorMessage(err, 'Could not load the mod sync time.'));
            }
        };

        loadStatus();

        // EventSource reconnects by itself after an error; `open` then means
        // there may be a gap to fill from /status.
        const source = new EventSource(EVENTS_URL);
        source.addEventListener('capture', (event) => {
            setLastReceivedAt(JSON.parse(event.data).last_received_at);
            setError(null);
        });
        source.addEventListener('error', () => {
            reconnecting = true;
        });
        source.addEventListener('open', () => {
            if (!reconnecting) return;
            reconnecting = false;
            loadStatus();
        });

        return () => {
            cancelled = true;
            source.close();
        };
    }, []);

    return {lastReceivedAt, error};
}
