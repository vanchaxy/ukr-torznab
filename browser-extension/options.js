const DEFAULT_BASE_URL = "http://localhost:8000";
const input = document.getElementById("baseUrl");
const status = document.getElementById("status");

function show(text, cls = "") {
  status.textContent = text;
  status.className = cls;
}

function normalized() {
  return (input.value.trim() || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

async function ensurePermission(url) {
  const origin = `${new URL(url).origin}/*`;
  if (await chrome.permissions.contains({ origins: [origin] })) return true;
  return chrome.permissions.request({ origins: [origin] });
}

chrome.storage.sync.get({ baseUrl: DEFAULT_BASE_URL }).then(({ baseUrl }) => {
  input.value = baseUrl;
});

document.getElementById("save").addEventListener("click", async () => {
  const url = normalized();
  try {
    new URL(url);
  } catch {
    return show("Not a valid URL", "err");
  }
  if (!(await ensurePermission(url))) return show("Permission to access this URL was denied", "err");
  await chrome.storage.sync.set({ baseUrl: url });
  show("Saved", "ok");
});

document.getElementById("test").addEventListener("click", async () => {
  const url = normalized();
  try {
    const resp = await fetch(`${url}/toloka/info/1`);
    const body = await resp.json();
    show(resp.ok ? `OK, indexer parser version ${body.parser_version}` : `HTTP ${resp.status}`, resp.ok ? "ok" : "err");
  } catch (e) {
    show(`Cannot reach ${url} (${e.message}). Save first if it's a new host.`, "err");
  }
});

document.getElementById("clear").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "clear-cache" });
  show("Cache cleared", "ok");
});
