// Shared helpers for the toloka/utp content scripts. Exposed as window.UkrTz.
(() => {
  const SKIP_REASONS = {
    UNEXPECTED_PAGE_STRUCTURE: ["Unexpected page layout", "The topic page has no single file list, so it couldn't be parsed."],
    INVALID_TORRENT: ["Invalid .torrent", "The downloaded .torrent file could not be decoded."],
    DISALLOWED_FILE_EXTENSION: [
      "Disallowed files",
      "The torrent contains files other than video, audio, subtitles, images or .ttf/.ifo/.bup/.txt/.otf (e.g. archives or disc images).",
    ],
    NO_VIDEO_FILES: ["No video files", "The torrent has no .mkv/.avi/.mp4/.ts/.vob/.m4v/.mpg files."],
    NO_IMDB_LINK: ["No IMDb link", "No IMDb id was found in the topic description."],
    IMDB_NOT_IN_DATABASE: ["IMDb id unknown", "The IMDb id is not in the local IMDb title.basics dataset."],
    TV_NO_SKYHOOK_METADATA: ["No Skyhook data", "Sonarr's Skyhook has no series for this IMDb id (no TVDB mapping)."],
    MOVIE_NO_SERVARR_METADATA: ["No Radarr data", "Radarr's metadata API has no movie for this IMDb id."],
    MOVIE_MULTIPLE_VIDEO_FILES: ["Multiple video files", "IMDb says it's a movie, but the torrent has more than one video file."],
    INCONSISTENT_FOLDER_STRUCTURE: [
      "Mixed folders",
      "Video files are split across several folders (e.g. a multi-season pack), which isn't supported.",
    ],
    CANNOT_DETERMINE_SEASON: ["Season unknown", "Couldn't determine the season from the title or file names."],
  };

  const STATES = {
    ok: ["ok", "Parsed"],
    skipped: ["warn", "Skipped"],
    pending: ["muted", "Waiting to be parsed"],
    not_downloaded: ["muted", "Not downloaded yet"],
    not_indexed: ["bad", "Not indexed"],
    untracked: ["bad", "Category not tracked"],
    error: ["bad", "Indexer error"],
  };

  // Tiny element builder. Strings become text nodes, so nothing from the API is parsed as HTML.
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) {
      if (c == null || c === false) continue;
      el.append(c instanceof Node ? c : String(c));
    }
    return el;
  }

  function getInfo(tracker, id) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: "info", tracker, id }, (resp) => {
          if (chrome.runtime.lastError) resolve({ ok: false, error: chrome.runtime.lastError.message });
          else resolve(resp || { ok: false, error: "No response" });
        });
      } catch (e) {
        // The extension was reloaded while this page stayed open.
        resolve({ ok: false, error: "Extension reloaded, refresh the page" });
      }
    });
  }

  function queue(concurrency) {
    let active = 0;
    const waiting = [];
    const next = () => {
      if (active >= concurrency || !waiting.length) return;
      active++;
      const { fn, resolve } = waiting.shift();
      fn().then(resolve).finally(() => {
        active--;
        next();
      });
    };
    return (fn) =>
      new Promise((resolve) => {
        waiting.push({ fn, resolve });
        next();
      });
  }

  // Runs cb(el) once, when el gets near the viewport.
  const lazyCallbacks = new WeakMap();
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        io.unobserve(e.target);
        const cb = lazyCallbacks.get(e.target);
        lazyCallbacks.delete(e.target);
        if (cb) cb(e.target);
      }
    },
    { rootMargin: "400px 0px" },
  );
  function whenVisible(el, cb) {
    lazyCallbacks.set(el, cb);
    io.observe(el);
  }

  function copyButton(text) {
    return h(
      "button",
      {
        class: "ukr-tz-copy",
        type: "button",
        title: "Copy",
        onclick: (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          navigator.clipboard.writeText(text).then(() => {
            ev.target.textContent = "✓";
            setTimeout(() => (ev.target.textContent = "⧉"), 1000);
          });
        },
      },
      "⧉",
    );
  }

  function chip(kind, text, title) {
    return h("span", { class: `ukr-tz-chip ukr-tz-${kind}`, title }, text);
  }

  function fmtSize(bytes) {
    if (!bytes) return null;
    const units = ["B", "KiB", "MiB", "GiB", "TiB"];
    let i = 0;
    let v = bytes;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    return `${v.toFixed(i ? 2 : 0)} ${units[i]}`;
  }

  function fmtDate(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString();
  }

  function episodesLabel(r) {
    if (r.content_type !== "tv") return null;
    const s = `S${String(r.season ?? 1).padStart(2, "0")}`;
    if (r.min_episode == null) return s;
    const a = String(r.min_episode).padStart(2, "0");
    const b = String(r.max_episode).padStart(2, "0");
    return r.min_episode === r.max_episode ? `${s}E${a}` : `${s}E${a}-${b}`;
  }

  // Normalised status for a toloka /info response, a utp /info response, or a fetch error.
  // `opts.category` lets list pages tell "not indexed" apart from "category not tracked".
  function status(tracker, resp, opts = {}) {
    if (!resp.ok) return { state: "error", detail: resp.error };
    if (tracker === "utp") return { state: "ok", release: resp.data };
    const d = resp.data;
    let state = d.state;
    if (state === "not_indexed" && opts.category && !d.tracked_categories.includes(String(opts.category))) {
      state = "untracked";
    }
    return { ...d, state };
  }

  function stateChips(st) {
    const [kind, label] = STATES[st.state] || ["muted", st.state];
    const chips = [];
    if (st.state === "skipped") {
      const [short, long] = SKIP_REASONS[st.reason] || [st.reason, ""];
      chips.push(chip(kind, `Skipped: ${short}`, long));
    } else if (st.state !== "ok") {
      chips.push(chip(kind, label, st.detail));
    }
    if (st.reparse_pending) chips.push(chip("muted", "re-parse queued", "The page changed or the parser was updated since the last parse"));
    if (st.topic && st.topic.stale) {
      chips.push(chip("muted", "stale", `Not seen on the tracker since ${fmtDate(st.topic.observed_at)}; search only returns topics seen in the last 2 days`));
    }
    const warnings = (st.release && st.release.warnings) || [];
    for (const w of warnings) chips.push(chip("warn", w));
    return chips;
  }

  // One-line summary for list pages.
  function badge(tracker, resp, opts) {
    const st = status(tracker, resp, opts);
    const r = st.release;
    const children = [h("span", { class: "ukr-tz-logo", title: "Ukr Torznab" }, "TZ")];
    if (r) {
      children.push(h("span", { class: "ukr-tz-name ukr-tz-ok-text", title: r.release_name }, r.release_name), copyButton(r.release_name));
    }
    children.push(...stateChips(st));
    return h("div", { class: "ukr-tz-badge" }, children);
  }

  function idLinks(r) {
    const links = [];
    if (r.imdb_id) links.push(h("a", { href: `https://www.imdb.com/title/${r.imdb_id}/`, target: "_blank" }, `IMDb ${r.imdb_id}`));
    if (r.tvdb_id) links.push(h("a", { href: `https://thetvdb.com/dereferrer/series/${r.tvdb_id}`, target: "_blank" }, `TVDB ${r.tvdb_id}`));
    if (r.tmdb_id) {
      const kind = r.content_type === "tv" ? "tv" : "movie";
      links.push(h("a", { href: `https://www.themoviedb.org/${kind}/${r.tmdb_id}`, target: "_blank" }, `TMDB ${r.tmdb_id}`));
    }
    if (!links.length) return null;
    return links.flatMap((a, i) => (i ? [" · ", a] : [a]));
  }

  function kvTable(rows) {
    const trs = rows
      .filter(([, v]) => v != null && v !== "" && !(Array.isArray(v) && !v.length))
      .map(([k, v]) => h("tr", {}, h("th", {}, k), h("td", {}, Array.isArray(v) && typeof v[0] === "string" ? v.join(", ") : v)));
    return h("table", { class: "ukr-tz-kv" }, trs);
  }

  function nameRow(label, value) {
    if (!value) return null;
    return h("div", { class: "ukr-tz-namerow" }, h("span", { class: "ukr-tz-label" }, label), h("code", {}, value), copyButton(value));
  }

  function yesNo(v) {
    return v == null ? null : v ? "yes" : "no";
  }

  function releaseSection(r) {
    return [
      nameRow("Release", r.release_name),
      nameRow("Cross-seed", r.xseed_name),
      nameRow("Folder", r.folder),
      kvTable([
        ["Title", [r.title, r.year && `(${r.year})`].filter(Boolean).join(" ")],
        ["Type", r.content_type],
        ["Ids", idLinks(r)],
        ["Episodes", episodesLabel(r)],
        ["Season complete", r.content_type === "tv" ? yesNo(r.season_complete) : null],
        ["Quality", r.quality],
        ["Resolution", r.resolution],
        ["Video codec", r.codec],
        ["Audio codec", r.acodec],
        ["HDR", r.hdr !== "sdr" ? r.hdr : null],
        ["Cut", r.cut],
        ["Ratio", r.ratio !== "standard" ? r.ratio : null],
        ["Hybrid", r.hybrid ? "yes" : null],
        ["Audio", r.audio_types],
        ["Audio langs", r.audio_lang],
        ["Subtitles", r.subtitle_lang],
        ["Studios", r.audio_sources],
        ["Group", r.release_group],
        ["Author", r.author],
        ["Size", fmtSize(r.torrent_size)],
        ["Registered", fmtDate(r.registered_at)],
      ]),
    ];
  }

  function audioTracksSection(tracks) {
    if (!tracks || !tracks.length) return null;
    return h(
      "details",
      { class: "ukr-tz-sub", open: true },
      h("summary", {}, `Audio tracks (${tracks.length})`),
      h(
        "table",
        { class: "ukr-tz-grid" },
        h("tr", {}, ["Mediainfo title", "Language", "Format", "→ Lang", "→ Type", "→ Studio"].map((c) => h("th", {}, c))),
        tracks.map((t) =>
          h("tr", {}, [t.title, t.language, [t.format, t.channels].filter(Boolean).join(", "), t.lang, t.type, t.studio || "—"].map((c) => h("td", {}, c ?? ""))),
        ),
      ),
    );
  }

  function episodesSection(episodes, videoFiles) {
    if (episodes && episodes.length) {
      return h(
        "details",
        { class: "ukr-tz-sub" },
        h("summary", {}, `File → episode map (${episodes.length})`),
        h(
          "table",
          { class: "ukr-tz-grid" },
          h("tr", {}, ["File", "Episode", "Renamed to"].map((c) => h("th", {}, c))),
          episodes.map((e) =>
            h(
              "tr",
              {},
              h("td", {}, e.file),
              h("td", {}, `S${String(e.season).padStart(2, "0")}E${String(e.episode).padStart(2, "0")}`),
              h("td", {}, e.renamed),
            ),
          ),
        ),
      );
    }
    if (videoFiles && videoFiles.length) {
      return h(
        "details",
        { class: "ukr-tz-sub" },
        h("summary", {}, `Video files (${videoFiles.length})`),
        h("ul", { class: "ukr-tz-files" }, videoFiles.map((f) => h("li", {}, f))),
      );
    }
    return null;
  }

  // Full panel for torrent/topic pages.
  function panel(tracker, resp) {
    const st = status(tracker, resp);
    const r = st.release;
    const [kind, label] = STATES[st.state] || ["muted", st.state];
    const body = [];

    const chips = stateChips(st);
    if (chips.length) body.push(h("div", { class: "ukr-tz-chips" }, chips));

    if (st.state === "skipped") {
      const [, long] = SKIP_REASONS[st.reason] || [st.reason, ""];
      body.push(h("p", { class: "ukr-tz-explain" }, h("b", {}, st.reason), long ? ` — ${long}` : ""));
    } else if (st.state === "not_indexed") {
      body.push(h("p", { class: "ukr-tz-explain" }, "The scraper hasn't seen this topic. Its category may not be in TOLOKA_CATEGORIES, or it was added after the last category walk."));
    } else if (st.state === "not_downloaded") {
      body.push(h("p", { class: "ukr-tz-explain" }, "The topic is listed, but its page or .torrent hasn't been downloaded yet."));
    } else if (st.state === "pending") {
      body.push(h("p", { class: "ukr-tz-explain" }, "The page is downloaded and waiting for ParseTopicsTask."));
    } else if (st.state === "error") {
      body.push(h("p", { class: "ukr-tz-explain" }, st.detail));
    }

    if (r) {
      body.push(...releaseSection(r));
      body.push(audioTracksSection(r.audio_tracks));
      body.push(episodesSection(r.episodes, r.video_files || r.files));
    }

    const meta = [];
    if (st.topic) {
      meta.push(`category ${st.topic.category}`);
      if (st.topic.observed_at) meta.push(`seen ${fmtDate(st.topic.observed_at)}`);
      if (st.topic.downloaded_at) meta.push(`downloaded ${fmtDate(st.topic.downloaded_at)}`);
    }
    if (st.parsed_at) meta.push(`parsed ${fmtDate(st.parsed_at)}`);
    if (st.release_parser_version != null) meta.push(`parser v${st.release_parser_version} (current v${st.parser_version})`);
    if (r && r.utp) meta.push(`UTP: ${[r.utp.category, r.utp.type, r.utp.resolution].filter(Boolean).join(" / ")}`);
    if (meta.length) body.push(h("div", { class: "ukr-tz-meta" }, meta.join(" · ")));

    return h(
      "details",
      { class: "ukr-tz-panel", open: true },
      h("summary", {}, h("span", { class: "ukr-tz-logo" }, "TZ"), " Ukr Torznab: ", h("span", { class: `ukr-tz-chip ukr-tz-${kind}` }, label)),
      h("div", { class: "ukr-tz-body" }, body),
    );
  }

  function loading(cls) {
    return h("div", { class: cls }, h("span", { class: "ukr-tz-logo" }, "TZ"), h("span", { class: "ukr-tz-chip ukr-tz-muted" }, "loading…"));
  }

  window.UkrTz = { h, getInfo, queue, whenVisible, badge, panel, loading };
})();
