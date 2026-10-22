(() => {
  const { getInfo, queue, whenVisible, badge, panel, loading } = window.UkrTz;
  const run = queue(6);

  function topicPageId() {
    const m = location.pathname.match(/^\/t(\d+)$/);
    if (m) return m[1];
    if (location.pathname === "/viewtopic.php") return new URLSearchParams(location.search).get("t");
    return null;
  }

  function showTopic(id) {
    const header = document.querySelector("h1 a.maintitle");
    const anchor = header ? header.closest("table") : null;
    if (!anchor) return;
    const placeholder = loading("ukr-tz-panel");
    anchor.after(placeholder);
    getInfo("toloka", id).then((resp) => placeholder.replaceWith(panel("toloka", resp)));
  }

  // tracker.php rows have the forum link in another cell; forum pages (/f16, /f16-90) carry it in the URL.
  function rowCategory(row) {
    const pageCat = location.pathname.match(/^\/f(\d+)(?:-\d+)?$/);
    if (pageCat) return pageCat[1];
    for (const a of row.querySelectorAll("a[href]")) {
      const m = a.getAttribute("href").match(/(?:[?&]f=|^\/?f)(\d+)/);
      if (m) return m[1];
    }
    return null;
  }

  function showList() {
    const links = document.querySelectorAll("td.topictitle a[href], a.topictitle[href]");
    for (const a of links) {
      const m = a.getAttribute("href").match(/^\/?t(\d+)$/);
      if (!m) continue;
      const cell = a.closest("td");
      if (!cell || cell.querySelector(".ukr-tz-badge")) continue;
      const row = cell.closest("tr");
      const slot = loading("ukr-tz-badge");
      cell.append(slot);
      whenVisible(slot, () =>
        run(() => getInfo("toloka", m[1])).then((resp) =>
          slot.replaceWith(badge("toloka", resp, { category: row && rowCategory(row) })),
        ),
      );
    }
  }

  const id = topicPageId();
  if (id) showTopic(id);
  else showList();
})();
