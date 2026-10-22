// Only the service worker talks to the indexer: content scripts on https pages can't fetch
// http://localhost (mixed content), and the indexer doesn't send CORS headers.

const DEFAULT_BASE_URL = "http://localhost:8000";
const CACHE_TTL_MS = 5 * 60 * 1000;
const cache = new Map(); // "tracker:id" -> { at, result }

async function baseUrl() {
  const { baseUrl } = await chrome.storage.sync.get({ baseUrl: DEFAULT_BASE_URL });
  return baseUrl.replace(/\/+$/, "");
}

async function fetchInfo(tracker, id) {
  const key = `${tracker}:${id}`;
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < CACHE_TTL_MS) return hit.result;

  const url = `${await baseUrl()}/${tracker}/info/${encodeURIComponent(id)}`;
  let result;
  try {
    const resp = await fetch(url);
    const body = await resp.json().catch(() => null);
    result = resp.ok
      ? { ok: true, data: body }
      : { ok: false, error: (body && body.detail) || `HTTP ${resp.status}` };
  } catch (e) {
    return { ok: false, error: `Indexer unreachable at ${url}` };
  }
  if (result.ok) cache.set(key, { at: Date.now(), result });
  return result;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "info") {
    fetchInfo(msg.tracker, msg.id).then(sendResponse);
    return true; // async response
  }
  if (msg && msg.type === "clear-cache") {
    cache.clear();
    sendResponse({ ok: true });
  }
  return false;
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.baseUrl) cache.clear();
});
