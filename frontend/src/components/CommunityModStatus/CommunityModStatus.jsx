/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-19
// "Mod sync: <local date/time>" for the Dashboard header.
import useCommunityModStatus from './useCommunityModStatus';

/** The time to show, in the browser's locale and time zone. */
export function formatSyncTime(isoTime) {
    if (!isoTime) return 'never';
    return new Date(isoTime).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'medium'});
}

const CommunityModStatus = () => {
    const {lastReceivedAt, error} = useCommunityModStatus();

    return (
        <div className="community-mod-status" title={error ?? 'Last update received from the community mod'}>
            Mod sync: {error ? 'unavailable' : formatSyncTime(lastReceivedAt)}
        </div>
    );
};

export default CommunityModStatus;
