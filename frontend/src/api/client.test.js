/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
import {describe, expect, it} from 'vitest';
import {api, errorMessage, SERVER_UNREACHABLE} from './client';
import {fakeApi, NETWORK_ERROR} from '../test/fakeApi';

/** The error a request rejects with, given what the fake server replies. */
const failWith = async (reply) => {
    fakeApi(() => reply);
    try {
        await api.get('/api/factions/summary');
    } catch (error) {
        return error;
    }
    throw new Error('expected the request to fail');
};

describe('errorMessage', () => {
    it("shows the backend's own message", async () => {
        const error = await failWith({status: 404, data: {error: 'Faction 9 not found.'}});
        expect(errorMessage(error, 'Load failed.')).toBe('Faction 9 not found.');
    });

    it('falls back with the status when the reply has no message', async () => {
        const error = await failWith({status: 502, data: '<html>Bad Gateway</html>'});
        expect(errorMessage(error, 'Load failed.')).toBe('Load failed. (HTTP 502)');
    });

    it('says the server is unreachable when nothing answered', async () => {
        const error = await failWith(NETWORK_ERROR);
        expect(errorMessage(error)).toBe(SERVER_UNREACHABLE);
    });

    it('reports a timeout distinctly', () => {
        expect(errorMessage({code: 'ECONNABORTED'})).toBe('The server took too long to respond.');
    });
});

describe('request timeouts', () => {
    it('gives captures a much longer ceiling than ordinary requests', async () => {
        const requests = fakeApi(() => ({status: 200, data: {}}));
        await api.get('/api/factions/summary');
        await api.post('/api/capture-screen/gifts');
        const [ordinary, capture] = requests.map(r => r.config.timeout);
        expect(ordinary).toBe(30_000);
        expect(capture).toBe(10 * 60_000);
    });
});
