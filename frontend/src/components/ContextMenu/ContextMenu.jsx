/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import {useEffect, useLayoutEffect, useRef, useState} from 'react';
import './ContextMenu.css';

// Gap kept between the menu and the viewport edge when it has to be nudged back on-screen.
const VIEWPORT_MARGIN = 8;

/**
 * Floating menu rendered at `position` (viewport coords). Closes on outside click,
 * another right-click, Escape, scroll, or resize. Pair with `useContextMenu`.
 *
 * items: [{label: string, onSelect: () => void, disabled?: boolean}]
 */
// ai: claude-opus-5-5 | 2026-10-17
const ContextMenu = ({position, items, onClose}) => {
    const menuRef = useRef(null);
    const [adjusted, setAdjusted] = useState(position);

    // Measure after layout and shift the menu back inside the viewport if it would overflow
    // (e.g. right-clicking near the right or bottom edge). Runs before paint, so no flicker.
    useLayoutEffect(() => {
        if (!position || !menuRef.current) {
            setAdjusted(position);
            return;
        }
        const {width, height} = menuRef.current.getBoundingClientRect();
        setAdjusted({
            x: Math.max(VIEWPORT_MARGIN, Math.min(position.x, window.innerWidth - width - VIEWPORT_MARGIN)),
            y: Math.max(VIEWPORT_MARGIN, Math.min(position.y, window.innerHeight - height - VIEWPORT_MARGIN)),
        });
    }, [position]);

    useEffect(() => {
        if (!position) return;
        const onKeyDown = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('click', onClose);
        window.addEventListener('contextmenu', onClose);
        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('scroll', onClose, true);
        window.addEventListener('resize', onClose);
        return () => {
            window.removeEventListener('click', onClose);
            window.removeEventListener('contextmenu', onClose);
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('scroll', onClose, true);
            window.removeEventListener('resize', onClose);
        };
    }, [position, onClose]);

    if (!position) return null;

    const {x, y} = adjusted ?? position;

    return (
        <div
            ref={menuRef}
            className="context-menu"
            role="menu"
            style={{top: y, left: x}}
            onClick={(e) => e.stopPropagation()}
        >
            {items.map((item) => (
                <button
                    key={item.label}
                    type="button"
                    role="menuitem"
                    className="context-menu-item"
                    disabled={item.disabled}
                    onClick={() => {
                        onClose();
                        item.onSelect();
                    }}
                >
                    {item.label}
                </button>
            ))}
        </div>
    );
};

export default ContextMenu;
