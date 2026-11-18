/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-sonnet-5 | 2026-09-18
import { useRef, useState } from 'react';
import { api, errorMessage } from '../../api/client';
import { useCaptureBusy } from '../../hooks/useCaptureBusy';

// Minimum drag distance (in displayed, on-screen pixels) before a drag counts
// as a real box rather than an accidental click.
const MIN_DRAG_PX = 6;

const KIND_OPTIONS = [
  { value: 'hostile_ship', label: 'Hostile Ship Icon' },
  { value: 'skull_glyph', label: 'Skull Glyph (danger)' },
  { value: 'diamond_glyph', label: 'Diamond Glyph (bounty)' },
];

// Bootstraps/extends the combat template lists (hostile ship icons, and the
// skull/diamond label glyphs) from the running app instead of hand-editing
// settings.yaml and snippet files: grabs a fresh screenshot of the game
// window, lets you draw a box around the thing you want (a ship you just
// selected in-game, or a glyph visible in its label), and saves that crop as
// a new template of the chosen kind (updating settings.yaml automatically).
const HostileTemplateCapture = () => {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState('hostile_ship');
  const [capturing, setCapturing] = useState(false);
  const [saving, setSaving] = useState(false);
  // ai: claude-opus-5-5 | 2026-11-06 — disabled while any capture runs, on any page
  const captureBusy = useCaptureBusy();
  const [screenshot, setScreenshot] = useState(null); // { imageBase64, width, height, systemName }
  const [displayBox, setDisplayBox] = useState(null); // {left, top, width, height} in on-screen px, for the overlay
  const [naturalBox, setNaturalBox] = useState(null); // {x, y, w, h} in image-native px, for the save request
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [templateCount, setTemplateCount] = useState(null);

  const imgWrapRef = useRef(null);
  const imgRef = useRef(null);
  const dragStartRef = useRef(null);
  const draggingRef = useRef(false);

  const handleCapture = async () => {
    setCapturing(true);
    setError(null);
    setMessage(null);
    setDisplayBox(null);
    setNaturalBox(null);
    try {
      const response = await api.post('/api/capture-screen/hostile-template/capture');
      const data = response.data;
      setScreenshot({
        imageBase64: data.image_base64,
        width: data.width,
        height: data.height,
        systemName: data.system_name,
      });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setCapturing(false);
    }
  };

  const relativePoint = (e) => {
    const rect = imgWrapRef.current.getBoundingClientRect();
    const x = Math.min(Math.max(e.clientX - rect.left, 0), rect.width);
    const y = Math.min(Math.max(e.clientY - rect.top, 0), rect.height);
    return { x, y, rect };
  };

  const handleMouseDown = (e) => {
    if (!screenshot) return;
    const { x, y } = relativePoint(e);
    dragStartRef.current = { x, y };
    draggingRef.current = true;
    setNaturalBox(null);
    setDisplayBox({ left: x, top: y, width: 0, height: 0 });
  };

  const handleMouseMove = (e) => {
    if (!draggingRef.current) return;
    const { x, y } = relativePoint(e);
    const start = dragStartRef.current;
    setDisplayBox({
      left: Math.min(start.x, x),
      top: Math.min(start.y, y),
      width: Math.abs(x - start.x),
      height: Math.abs(y - start.y),
    });
  };

  const finishDrag = (e) => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    const { rect } = relativePoint(e);
    if (!displayBox || displayBox.width < MIN_DRAG_PX || displayBox.height < MIN_DRAG_PX) {
      setDisplayBox(null);
      return;
    }
    const img = imgRef.current;
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;
    setNaturalBox({
      x: Math.round(displayBox.left * scaleX),
      y: Math.round(displayBox.top * scaleY),
      w: Math.round(displayBox.width * scaleX),
      h: Math.round(displayBox.height * scaleY),
    });
  };

  const handleSave = async () => {
    if (!naturalBox) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await api.post('/api/capture-screen/hostile-template/save', { ...naturalBox, kind });
      const data = response.data;
      setMessage(`Added ${data.filename}.`);
      setTemplateCount(data.templates.length);
      setDisplayBox(null);
      setNaturalBox(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const handleClearBox = () => {
    setDisplayBox(null);
    setNaturalBox(null);
  };

  const handleKindChange = (nextKind) => {
    setKind(nextKind);
    setTemplateCount(null); // stale count belonged to the previous kind's list
    setMessage(null);
  };

  if (!open) {
    return (
      <button className="btn-outline" onClick={() => setOpen(true)} style={{ marginBottom: '1rem' }}>
        + Add Combat Template
      </button>
    );
  }

  const kindLabel = KIND_OPTIONS.find((o) => o.value === kind)?.label || kind;

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h2 style={{ margin: 0 }}>Add Combat Template</h2>
        <button className="btn-outline" onClick={() => setOpen(false)}>Close</button>
      </div>
      <p style={{ fontSize: '0.85rem', color: 'var(--c-muted)', marginBottom: '1rem' }}>
        In-game, select a hostile ship on the starmap first. Then capture the screen here, draw a
        box around the ship's icon (or, once a ship's label is visible, around the skull/diamond
        glyph after its name), pick what kind of template it is, and add it — this updates
        settings.yaml automatically. You can draw multiple boxes from the same capture.
      </p>

      <div style={{ display: 'flex', gap: '1.25rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {KIND_OPTIONS.map((opt) => (
          <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0, cursor: 'pointer' }}>
            <input
              type="radio"
              name="template-kind"
              value={opt.value}
              checked={kind === opt.value}
              onChange={() => handleKindChange(opt.value)}
              style={{ width: 'auto' }}
            />
            <span style={{ fontSize: '0.85rem', color: 'var(--c-text)' }}>{opt.label}</span>
          </label>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center' }}>
        <button className="btn-capture" onClick={handleCapture} disabled={capturing || captureBusy}>
          {capturing ? 'Capturing…' : screenshot ? 'Recapture Screen' : 'Capture Screen'}
        </button>
        {screenshot?.systemName && (
          <span style={{ fontSize: '0.85rem', color: 'var(--c-muted)' }}>System: {screenshot.systemName}</span>
        )}
        {templateCount != null && (
          <span style={{ fontSize: '0.85rem', color: 'var(--c-muted)' }}>
            {templateCount} {kindLabel} template{templateCount === 1 ? '' : 's'} configured
          </span>
        )}
      </div>

      {error && <div style={{ color: 'var(--c-danger)', marginBottom: '1rem' }}>{error}</div>}
      {message && <div style={{ color: 'var(--c-success)', marginBottom: '1rem' }}>{message}</div>}

      {screenshot && (
        <>
          <div
            ref={imgWrapRef}
            style={{ position: 'relative', display: 'inline-block', cursor: 'crosshair', userSelect: 'none' }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={finishDrag}
            onMouseLeave={(e) => { if (draggingRef.current) finishDrag(e); }}
          >
            <img
              ref={imgRef}
              src={`data:image/png;base64,${screenshot.imageBase64}`}
              alt="Captured game screen"
              draggable={false}
              onDragStart={(e) => e.preventDefault()}
              style={{ display: 'block', maxWidth: '100%', height: 'auto', borderRadius: '4px' }}
            />
            {displayBox && (
              <div
                style={{
                  position: 'absolute',
                  left: displayBox.left,
                  top: displayBox.top,
                  width: displayBox.width,
                  height: displayBox.height,
                  border: '2px solid var(--c-success)',
                  backgroundColor: 'rgba(61, 220, 132, 0.15)',
                  pointerEvents: 'none',
                }}
              />
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', alignItems: 'center' }}>
            <button className="btn-capture" onClick={handleSave} disabled={!naturalBox || saving || captureBusy}>
              {saving
                ? 'Saving…'
                : kind === 'hostile_ship'
                  ? `Add This for ${screenshot.systemName || 'this system'}`
                  : `Add This as ${kindLabel}`}
            </button>
            <button className="btn-outline" onClick={handleClearBox} disabled={!displayBox}>
              Clear Box
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default HostileTemplateCapture;
