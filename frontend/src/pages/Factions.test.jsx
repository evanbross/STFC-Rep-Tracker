/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
// Faction add/edit on the Factions page, driven through the rendered form.
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import Factions from './Factions';
import {fakeApi, jsonBody} from '../test/fakeApi';

// A GET /api/factions row (factions_dao._row_to_dict). Factions are identified by `code`.
const FEDERATION = {
    code: 'FED', name: 'Federation', on_chart: 1, color: '#0080ff',
    reputation_table_name: 'fkr_reputations', display_order: 1, reputation_dao_name: 'FKRReputationsDAO',
    snippet_selected_button: 'Selected-Button-Fed.jpg', snippet_unselected: 'Unselected-Button-Fed.jpg',
    spocks_resource_id: 970475396,
};

const REPUTATION_TYPES = [
    {table_name: 'fkr_reputations', dao_name: 'FKRReputationsDAO'},
    {table_name: 'terran_reputations', dao_name: 'TerranReputationsDAO'},
];

let alertSpy;
beforeEach(() => {
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
});

/** A fake backend for the page; `saveReply` answers the POST/PUT. */
const fakeBackend = (saveReply) => fakeApi(({method, url}) => {
    if (method === 'get' && url === '/api/factions') return {status: 200, data: [FEDERATION]};
    if (method === 'get' && url === '/api/reputations/types') return {status: 200, data: REPUTATION_TYPES};
    return saveReply;
});

const factionListLoads = (requests) => requests.filter(r => r.method === 'get' && r.url === '/api/factions').length;

const change = (label, value) => fireEvent.change(screen.getByLabelText(label), {target: {value}});

describe('Factions page', () => {
    it("edits a faction: prefilled form, the type's DAO follows, PUT by code without the id", async () => {
        const requests = fakeBackend({status: 200, data: {}});
        render(<Factions/>);
        fireEvent.click(await screen.findByRole('button', {name: 'Edit'}));

        expect(screen.getByRole('heading', {name: 'Edit Faction'})).toBeTruthy();
        expect(screen.getByLabelText('Faction Name:').value).toBe('Federation');
        expect(screen.getByLabelText("Spock's Club Resource ID:").value).toBe('970475396');

        change('Faction Name:', 'United Federation');
        change('Reputation Type:', 'terran_reputations');
        fireEvent.click(screen.getByRole('button', {name: 'Save Faction'}));

        await waitFor(() => expect(screen.queryByRole('heading', {name: 'Edit Faction'})).toBeNull());
        const save = requests.find(r => r.method === 'put');
        expect(save.url).toBe('/api/factions/FED');
        expect(jsonBody(save)).toEqual({
            name: 'United Federation', code: 'FED', color: '#0080ff',
            reputation_table_name: 'terran_reputations', reputation_dao_name: 'TerranReputationsDAO',
            on_chart: 1, display_order: 1,
            snippet_selected_button: 'Selected-Button-Fed.jpg', snippet_unselected: 'Unselected-Button-Fed.jpg',
            spocks_resource_id: 970475396,
        });
        expect(factionListLoads(requests)).toBe(2);
    });

    it('adds a faction with POST', async () => {
        const requests = fakeBackend({status: 201, data: {}});
        render(<Factions/>);
        fireEvent.click(await screen.findByRole('button', {name: 'Add New Faction'}));

        change('Faction Name:', 'Romulan');
        change('Code:', 'ROM');
        fireEvent.click(screen.getByRole('button', {name: 'Save Faction'}));

        await waitFor(() => expect(requests.some(r => r.method === 'post')).toBe(true));
        const save = requests.find(r => r.method === 'post');
        expect(save.url).toBe('/api/factions');
        expect(jsonBody(save)).toMatchObject({name: 'Romulan', code: 'ROM', reputation_table_name: ''});
        expect(jsonBody(save)).not.toHaveProperty('id');
    });

    it('starts Add empty after a cancelled Edit, and saves it as a new faction', async () => {
        const requests = fakeBackend({status: 201, data: {}});
        render(<Factions/>);
        fireEvent.click(await screen.findByRole('button', {name: 'Edit'}));
        fireEvent.click(screen.getByRole('button', {name: 'Cancel'}));

        fireEvent.click(screen.getByRole('button', {name: 'Add New Faction'}));

        expect(screen.getByRole('heading', {name: 'Add New Faction'})).toBeTruthy();
        expect(screen.getByLabelText('Faction Name:').value).toBe('');
        change('Faction Name:', 'Romulan');
        change('Code:', 'ROM');
        fireEvent.click(screen.getByRole('button', {name: 'Save Faction'}));
        await waitFor(() => expect(requests.some(r => r.method === 'post')).toBe(true));
        expect(requests.some(r => r.method === 'put')).toBe(false);
    });

    it("keeps the form open and shows the backend's reason when saving fails", async () => {
        fakeBackend({status: 409, data: {error: "Another faction already uses code 'FED'."}});
        render(<Factions/>);
        fireEvent.click(await screen.findByRole('button', {name: 'Edit'}));

        fireEvent.click(screen.getByRole('button', {name: 'Save Faction'}));

        await waitFor(() => expect(alertSpy).toHaveBeenCalled());
        expect(alertSpy).toHaveBeenCalledWith("Failed to save faction: Another faction already uses code 'FED'.");
        expect(screen.getByRole('heading', {name: 'Edit Faction'})).toBeTruthy();
    });
});
