/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
// A fake transport for the shared axios instance.
//
// It swaps the adapter (the part that does the network I/O), not api.get/post,
// so every request still passes through the real request/response
// interceptors: the capture timeout in client.js and the busy counter in
// useCaptureBusy.js. These tests check the frontend's own logic against the
// response shapes it expects; they don't check those shapes against Flask.
// The backend's API contract tests (tests/, marked `db`) do that.
import {AxiosError} from 'axios';
import {api} from '../api/client';

const originalAdapter = api.defaults.adapter;

/** Put the real adapter back (setup.js does this after every test). */
export function restoreApiAdapter() {
    api.defaults.adapter = originalAdapter;
}

/** Stands in for a request that never got a response (backend not running). */
export const NETWORK_ERROR = Symbol('networkError');

/**
 * Route every request on `api` to `handler`, and record each one.
 *
 * handler({method, url, params, data, config}) returns (or resolves to)
 * `{status, data}`, or NETWORK_ERROR. A status outside 2xx rejects with an
 * AxiosError carrying that response, like a real server reply would.
 * `data` is the request body as sent: a string for JSON, a FormData for uploads.
 *
 * Returns the array of recorded requests.
 */
export function fakeApi(handler) {
    const requests = [];
    api.defaults.adapter = async (config) => {
        const request = {
            method: config.method,
            url: config.url,
            params: config.params,
            data: config.data,
            config,
        };
        requests.push(request);
        const reply = await handler(request);
        if (reply === NETWORK_ERROR) {
            throw new AxiosError('Network Error', AxiosError.ERR_NETWORK, config);
        }
        const response = {
            data: reply.data,
            status: reply.status,
            statusText: String(reply.status),
            headers: {},
            config,
        };
        if (reply.status >= 200 && reply.status < 300) return response;
        throw new AxiosError(
            `Request failed with status code ${reply.status}`,
            AxiosError.ERR_BAD_RESPONSE,
            config,
            null,
            response,
        );
    };
    return requests;
}

/** The JSON body a request sent, parsed. */
export const jsonBody = (request) => JSON.parse(request.data);

/** A promise plus its resolve function, for holding a reply until the test releases it. */
export function deferred() {
    let resolve;
    const promise = new Promise((done) => {
        resolve = done;
    });
    return {promise, resolve};
}
