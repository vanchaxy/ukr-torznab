# Ukr Torznab Inspector

Chrome extension (Manifest V3, no build step) that overlays the toloka-torznab parser output on toloka.to and utp.to.

| Page | Shows |
|---|---|
| `toloka.to/tracker.php?…`, `toloka.to/fNN` | Under each topic: release name, or the skip reason / "not indexed" / "category not tracked", plus a `stale` marker when the topic is outside the 2-day search window |
| `toloka.to/tNNN` | Panel: state and explanation, release / cross-seed / folder names, IMDb/TVDB/TMDB links, all detected attributes, parse timestamps and parser version, file → episode → renamed-file table |
| `utp.to/torrents` | Under each torrent: release name and warnings (missing ids, unknown quality/audio, no Ukrainian audio) |
| `utp.to/torrents/NNN` | Panel like toloka's, plus the per-audio-track table (mediainfo title → language, type, studio) |

## Install

1. Run the indexer (it serves `/toloka/info/{id}` and `/utp/info/{id}`; the UTP one needs `UTP_API_KEY`).
2. Open `chrome://extensions`, enable **Developer mode**, click **Load unpacked** and pick this folder.
3. Click the extension icon and set the indexer URL. The default is `http://localhost:8000`. Chrome asks for
   permission when the URL is a host other than localhost/127.0.0.1.

## How it works

- `background.js` is the only part that calls the indexer. Content scripts on https pages can't reach
  `http://localhost` (mixed content, utp.to's CSP), and the indexer sends no CORS headers. Successful answers are
  cached for 5 minutes. Use **Clear cache** in the popup after a re-parse.
- List pages load rows lazily as they scroll into view: up to 6 parallel requests for toloka, and one at a time
  for UTP, because the indexer's UTP client is limited to 1 req/s.
- The utp.to list is re-rendered by Livewire, so `utp.js` watches the DOM and re-attaches badges. UNIT3D selectors
  are in `SEL` at the top of `utp.js`.
