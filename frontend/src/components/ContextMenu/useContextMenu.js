/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import {useCallback, useState} from 'react';

/**
 * State + handlers for a right-click menu.
 *
 * Spread `bind(enabled)` onto the trigger element and pass `position` / `close`
 * to <ContextMenu>. `enabled` lets the caller suppress the menu (e.g. while busy).
 */
// ai: claude-opus-5-5 | 2026-10-17
const useContextMenu = () => {
    const [position, setPosition] = useState(null); // null = closed, {x, y} = open at cursor

    const close = useCallback(() => setPosition(null), []);

    const bind = useCallback((enabled = true) => ({
        onContextMenu: (e) => {
            e.preventDefault();
            // Keep the window-level close listener in <ContextMenu> from immediately
            // closing a menu that is being re-opened at a new spot.
            e.stopPropagation();
            if (enabled) setPosition({x: e.clientX, y: e.clientY});
        },
    }), []);

    return {position, close, bind};
};

export default useContextMenu;
