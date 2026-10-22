(() => {
  const { getInfo, queue, whenVisible, badge, panel, loading } = window.UkrTz;
  // The indexer's UTP client is limited to 1 req/s, so don't pile up parallel requests.
  const run = queue(1);

  // UNIT3D markup; keep the selectors here so they're easy to adjust.
  const SEL = {
    // Panel goes below the download buttons, above MediaInfo; later entries are fallbacks.
    detailAnchors: ["main menu.torrent__buttons", "main section.meta"],
    detailFallback: "main",
    listName: "a.torrent-search--list__name[href]",
    listCell: "td.torrent-search--list__overview",
  };

  function torrentId(href) {
    const m = (href || "").match(/\/torrents\/(\d+)\/?$/);
    return m ? m[1] : null;
  }

  function findAnchor() {
    for (const sel of SEL.detailAnchors) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    return null;
  }

  // The page can still be rendering at document_idle; wait up to 5 s for the anchor.
  function waitForAnchor() {
    return new Promise((resolve) => {
      const found = findAnchor();
      if (found) return resolve(found);
      const mo = new MutationObserver(() => {
        const el = findAnchor();
        if (el) {
          mo.disconnect();
          resolve(el);
        }
      });
      mo.observe(document.body, { childList: true, subtree: true });
      setTimeout(() => {
        mo.disconnect();
        resolve(null);
      }, 5000);
    });
  }

  async function showDetail(id) {
    const placeholder = loading("ukr-tz-panel ukr-tz-dark");
    const anchor = await waitForAnchor();
    if (anchor) anchor.after(placeholder);
    else {
      const main = document.querySelector(SEL.detailFallback);
      if (!main) return;
      main.prepend(placeholder);
    }
    getInfo("utp", id).then((resp) => {
      const el = panel("utp", resp);
      el.classList.add("ukr-tz-dark");
      placeholder.replaceWith(el);
    });
  }

  // Livewire re-renders the list in place (filters, paging), so rescan on DOM changes and
  // reuse finished badges by id.
  const done = new Map(); // id -> response

  function render(cell, id) {
    const old = cell.querySelector(":scope > .ukr-tz-badge");
    if (old && old.dataset.id === id) return;
    if (old) old.remove();

    let el;
    if (done.has(id)) {
      el = badge("utp", done.get(id));
    } else {
      el = loading("ukr-tz-badge");
      whenVisible(el, () =>
        run(() => getInfo("utp", id)).then((resp) => {
          done.set(id, resp);
          if (el.isConnected) {
            const fresh = badge("utp", resp);
            fresh.dataset.id = id;
            fresh.classList.add("ukr-tz-dark");
            el.replaceWith(fresh);
          }
        }),
      );
    }
    el.dataset.id = id;
    el.classList.add("ukr-tz-dark");
    cell.append(el);
  }

  function scanList() {
    for (const a of document.querySelectorAll(SEL.listName)) {
      const id = torrentId(a.getAttribute("href"));
      const cell = a.closest(SEL.listCell) || a.parentElement;
      if (id && cell) render(cell, id);
    }
  }

  const detailId = location.pathname.match(/^\/torrents\/(\d+)\/?$/);
  if (detailId) {
    showDetail(detailId[1]);
    return;
  }
  if (!/^\/torrents\/?$/.test(location.pathname)) return;

  scanList();
  let pending = false;
  new MutationObserver(() => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      scanList();
    });
  }).observe(document.body, { childList: true, subtree: true });
})();
