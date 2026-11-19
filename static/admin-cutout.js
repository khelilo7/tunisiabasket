// Admin: take the player(s) out of a photo, in the browser (MediaPipe Interactive Segmenter, Apache-2.0, files in /vendor/mediapipe: nothing is uploaded, nothing is installed).
// You point at the player (one click on him; another click on a second player adds him): the model draws his outline at the photo's full size.
//   const canvas = await Cutout.cut(image, [{ x: 0.5, y: 0.45 }])     points as fractions of the photo; the people they touch are kept
//   Cutout.picker(box, image, onCut)                                    draws the photo small in `box`, each click adds a person; onCut(canvas) is called every time
// A cut-out is a canvas with the people only (transparent elsewhere, soft edges), cropped to them, or null when the click found nobody.
(function () {
  let segmenter = null, loading = null;

  async function load() {
    if (segmenter) return segmenter;
    if (!loading) loading = (async () => {
      const vision = await import('/vendor/mediapipe/vision_bundle.mjs');
      const files = await vision.FilesetResolver.forVisionTasks('/vendor/mediapipe/wasm');
      segmenter = await vision.InteractiveSegmenterLegacy.createFromOptions(files, {
        baseOptions: { modelAssetPath: '/vendor/mediapipe/magic_touch.tflite' }, outputConfidenceMasks: true, outputCategoryMask: false,
      });
      return segmenter;
    })().catch(e => { loading = null; throw e; });
    return loading;
  }

  async function cut(img, points) {
    const seg = await load();
    const iw = img.naturalWidth || img.width, ih = img.naturalHeight || img.height, scale = Math.min(1, 1800 / Math.max(iw, ih));
    const W = Math.round(iw * scale), H = Math.round(ih * scale);
    const src = document.createElement('canvas'); src.width = W; src.height = H; src.getContext('2d').drawImage(img, 0, 0, W, H);
    let acc = null, mw = 0, mh = 0;
    for (const p of (points && points.length ? points : [{ x: 0.5, y: 0.45 }])) {
      const m = seg.segment(src, { keypoint: { x: Math.min(1, Math.max(0, p.x)), y: Math.min(1, Math.max(0, p.y)) } }).confidenceMasks[0];
      mw = m.width; mh = m.height; const a = m.getAsFloat32Array();
      acc = acc || new Float32Array(a.length);
      for (let i = 0; i < a.length; i++) if (a[i] > acc[i]) acc[i] = a[i];
      m.close && m.close();
    }
    const mask = document.createElement('canvas'); mask.width = mw; mask.height = mh;
    const mc = mask.getContext('2d'), id = mc.createImageData(mw, mh);
    for (let i = 0; i < acc.length; i++) { id.data[i * 4] = id.data[i * 4 + 1] = id.data[i * 4 + 2] = 255; id.data[i * 4 + 3] = acc[i] > 0.5 ? 255 : 0; }
    mc.putImageData(id, 0, 0);
    const out = document.createElement('canvas'); out.width = W; out.height = H;
    const oc = out.getContext('2d'); oc.drawImage(src, 0, 0); oc.globalCompositeOperation = 'destination-in'; oc.imageSmoothingQuality = 'high';
    oc.filter = `blur(${Math.max(0.8, W / 1500).toFixed(1)}px)`; oc.drawImage(mask, 0, 0, W, H);          // a slightly soft edge
    const d = oc.getImageData(0, 0, W, H).data; let x0 = W, y0 = H, x1 = 0, y1 = 0;
    for (let y = 0; y < H; y += 2) for (let x = 0; x < W; x += 2) if (d[(y * W + x) * 4 + 3] > 40) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    if (x1 <= x0 || y1 <= y0) return null;
    const pad = 3, cx = Math.max(0, x0 - pad), cy = Math.max(0, y0 - pad), cw = Math.min(W, x1 + pad) - cx, ch = Math.min(H, y1 + pad) - cy;
    const crop = document.createElement('canvas'); crop.width = cw; crop.height = ch; crop.getContext('2d').drawImage(out, cx, cy, cw, ch, 0, 0, cw, ch);
    return crop;
  }

  // the photo, small, with a dot per person pointed at; the first cut is made at once on the middle of the photo
  function picker(box, img, onCut) {
    const pts = [], iw = img.naturalWidth || img.width, ih = img.naturalHeight || img.height, w = Math.min(300, iw), h = Math.round(w * ih / iw);
    box.innerHTML = `<div style="position:relative;display:inline-block;cursor:crosshair"><canvas width="${w}" height="${h}" style="display:block;border-radius:10px;border:1px solid var(--line)"></canvas></div>
      <div class="small mut" id="cut-note" style="margin-top:4px"></div><button id="cut-reset" class="small">Start again</button>`;
    const cv = box.querySelector('canvas'), note = box.querySelector('#cut-note');
    const paint = () => { const c = cv.getContext('2d'); c.drawImage(img, 0, 0, w, h); pts.forEach((p, i) => { c.beginPath(); c.arc(p.x * w, p.y * h, 9, 0, 7); c.fillStyle = '#ff8a1f'; c.fill(); c.lineWidth = 2; c.strokeStyle = '#fff'; c.stroke(); c.fillStyle = '#10131c'; c.font = '700 11px system-ui'; c.textAlign = 'center'; c.fillText(i + 1, p.x * w, p.y * h + 4); }); };
    let busy = 0;
    const run = async () => {
      const mine = ++busy; note.textContent = 'Extracting…'; paint();
      try { const c = await cut(img, pts); if (mine !== busy) return; note.textContent = c ? (pts.length ? 'Click on another player to add him.' : 'Click on the player to choose him (the middle of the photo was used).') : 'Nobody found there: click on the player.'; onCut(c); }
      catch (e) { if (mine === busy) { note.textContent = 'The cut-out is not available: ' + (e.message || e); onCut(null); } }
    };
    cv.onclick = e => { const r = cv.getBoundingClientRect(); pts.push({ x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height }); run(); };
    box.querySelector('#cut-reset').onclick = () => { pts.length = 0; run(); };
    run();
  }

  window.Cutout = { cut, picker, ready: load };
})();
