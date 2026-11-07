const $ = id => document.getElementById(id);
let connected = false;
let syncing = false;
const DB_NAME = "wasteops-driver-offline";
const DB_VERSION = 1;

function setStatus(message, type = "") {
  const element = $("status");
  element.textContent = message;
  element.className = "status " + type;
}
function setConnection() {
  const element = $("connection");
  element.textContent = navigator.onLine
    ? "Online · pending actions will sync when you sign in."
    : "Offline · cached stops are available and new actions will be queued on this device.";
  element.className = "status " + (navigator.onLine ? "ok" : "error");
}
function authHeaders() {
  return {
    "X-Driver-Id": $("driverId").value.trim(),
    "X-Driver-Token": $("token").value.trim(),
    "Content-Type": "application/json",
  };
}
function apiBase() {
  const configured = $("api").value.trim();
  if (!configured) return window.location.origin;
  let url;
  try { url = new URL(configured); }
  catch { throw new Error("Enter a valid absolute API URL, or leave this field empty to use the current site."); }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("API URL must use HTTP(S) and must not contain credentials, query parameters, or a fragment.");
  }
  const localHost = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.protocol !== "https:" && !localHost) throw new Error("Remote API hosts must use HTTPS to protect credentials in transit.");
  if (window.location.protocol === "https:" && url.protocol !== "https:") throw new Error("An HTTPS site cannot send credentials to an insecure HTTP API.");
  return url.origin + url.pathname.replace(/\/+$/, "");
}
async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) throw new Error("The request timed out after 15 seconds. Check API availability and try again.");
    throw new Error("Could not reach the API. Check the network connection and configured API URL, then try again.");
  } finally { clearTimeout(timer); }
}
async function request(path, options = {}) {
  const response = await fetchWithTimeout(apiBase() + path, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) {
    const error = new Error(typeof body.detail === "string" ? body.detail : "Request failed (" + response.status + ")");
    error.status = response.status;
    throw error;
  }
  return body;
}
function newIdempotencyKey() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
}
function openOfflineDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("jobs")) db.createObjectStore("jobs", { keyPath: "cacheKey" });
      if (!db.objectStoreNames.contains("actions")) db.createObjectStore("actions", { keyPath: "idempotencyKey" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Could not open offline storage"));
  });
}
function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Offline storage transaction failed"));
    transaction.onabort = () => reject(transaction.error || new Error("Offline storage transaction was aborted"));
  });
}
async function readAll(storeName) {
  const db = await openOfflineDb();
  try {
    const transaction = db.transaction(storeName, "readonly");
    const result = await new Promise((resolve, reject) => {
      const request = transaction.objectStore(storeName).getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
    await transactionDone(transaction);
    return result;
  } finally { db.close(); }
}
async function writeRecord(storeName, record) {
  const db = await openOfflineDb();
  try {
    const transaction = db.transaction(storeName, "readwrite");
    transaction.objectStore(storeName).put(record);
    await transactionDone(transaction);
  } finally { db.close(); }
}
async function deleteRecord(storeName, key) {
  const db = await openOfflineDb();
  try {
    const transaction = db.transaction(storeName, "readwrite");
    transaction.objectStore(storeName).delete(key);
    await transactionDone(transaction);
  } finally { db.close(); }
}
async function saveCachedJobs(driverId, jobs) {
  const db = await openOfflineDb();
  try {
    const transaction = db.transaction("jobs", "readwrite");
    const store = transaction.objectStore("jobs");
    const existing = await new Promise((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
    existing.filter(job => job.driverId === driverId).forEach(job => store.delete(job.cacheKey));
    jobs.forEach(job => store.put({ ...job, driverId, cacheKey: driverId + ":" + job.id }));
    await transactionDone(transaction);
  } finally { db.close(); }
}
async function cachedJobs(driverId) {
  return (await readAll("jobs")).filter(job => job.driverId === driverId);
}
async function clearCachedJobs(driverId) {
  const jobs = await cachedJobs(driverId);
  for (const job of jobs) await deleteRecord("jobs", job.cacheKey);
}
async function queuedActions(driverId) {
  return (await readAll("actions"))
    .filter(action => action.driverId === driverId)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}
async function renderQueue() {
  const driverId = $("driverId").value.trim();
  const actions = driverId ? await queuedActions(driverId) : [];
  const root = $("pendingActions");
  root.replaceChildren();
  if (!actions.length) {
    root.textContent = "No pending actions for this driver.";
    $("syncPending").disabled = true;
    return;
  }
  $("syncPending").disabled = !connected || !navigator.onLine;
  for (const action of actions) {
    const row = document.createElement("div");
    row.className = "job";
    const label = document.createElement("span");
    label.textContent = action.status.toUpperCase() + " · job " + action.jobId.slice(0, 8) + (action.blocked ? " · needs attention: " + action.lastError : " · waiting to sync");
    row.append(label);
    if (action.blocked) {
      row.append(button("Discard", "danger", async () => {
        if (!confirm("Discard this unsent driver action? The server has not confirmed it.")) return;
        await deleteRecord("actions", action.idempotencyKey);
        await renderQueue();
        await loadJobs();
      }));
    }
    root.append(row);
  }
}
function button(label, cls, fn) {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  if (cls) element.className = cls;
  element.addEventListener("click", fn);
  return element;
}
async function renderJobs(jobs) {
  const root = $("jobs");
  root.replaceChildren();
  const actions = await queuedActions($("driverId").value.trim());
  const pendingByJob = new Map();
  for (const action of actions) {
    const current = pendingByJob.get(action.jobId) || [];
    current.push(action);
    pendingByJob.set(action.jobId, current);
  }
  for (const job of jobs) {
    const card = document.createElement("article");
    card.className = "job";
    const head = document.createElement("div");
    head.className = "job-head";
    const title = document.createElement("strong");
    title.textContent = job.bin_id;
    const status = document.createElement("span");
    status.className = "sub";
    status.textContent = job.status.toUpperCase();
    head.append(title, status);
    const details = document.createElement("p");
    details.className = "sub";
    details.textContent = "Job " + job.id.slice(0, 8) + " · " + Number(job.demand_liters).toFixed(1) + " L · priority " + Number(job.priority).toFixed(1) + " · " + job.latitude + ", " + job.longitude;
    card.append(head, details);
    const actionsRoot = document.createElement("div");
    actionsRoot.className = "actions";
    if (job.latitude !== null && job.longitude !== null) {
      const nav = document.createElement("a");
      nav.className = "link";
      nav.target = "_blank";
      nav.rel = "noopener noreferrer";
      nav.href = "https://www.google.com/maps/dir/?api=1&destination=" + encodeURIComponent(job.latitude + "," + job.longitude);
      nav.textContent = "Navigate";
      actionsRoot.append(nav);
    }
    const pending = pendingByJob.get(job.id) || [];
    if (pending.length) {
      const queued = document.createElement("span");
      queued.className = "sub";
      queued.textContent = "Pending sync: " + pending.map(item => item.status).join(" → ");
      actionsRoot.append(queued);
    } else {
      if (job.status === "assigned") actionsRoot.append(button("Start stop", "", () => transition(job.id, "in_progress")));
      if (job.status === "in_progress") {
        actionsRoot.append(button("Mark collected", "", () => transition(job.id, "completed")));
        actionsRoot.append(button("Report exception", "danger", () => transition(job.id, "exception")));
      }
    }
    card.append(actionsRoot);
    root.append(card);
  }
  if (!jobs.length) {
    const empty = document.createElement("div");
    empty.className = "panel sub";
    empty.textContent = "No assigned or in-progress jobs. Refresh after dispatch.";
    root.append(empty);
  }
}
async function loadJobs() {
  if (!connected) return setStatus("Enter driver credentials first.", "error");
  setStatus("Loading assigned jobs…");
  try {
    const jobs = await request("/api/v1/driver/jobs");
    await saveCachedJobs($("driverId").value.trim(), jobs);
    await renderJobs(jobs);
    setStatus("Loaded " + jobs.length + " assigned stops.", "ok");
  } catch (error) {
    if (!error.status || error.status >= 500) {
      const cached = await cachedJobs($("driverId").value.trim());
      await renderJobs(cached);
      setStatus(cached.length
        ? "Offline or API unavailable · showing " + cached.length + " cached stops. New actions will be queued locally."
        : "Offline or API unavailable · no previously cached stops on this device.", "error");
    } else {
      setStatus(error.message, "error");
    }
  }
  await renderQueue();
}
async function sendQueuedAction(action) {
  return request("/api/v1/driver/jobs/" + encodeURIComponent(action.jobId) + "/transition", {
    method: "POST",
    headers: { "Idempotency-Key": action.idempotencyKey },
    body: JSON.stringify({ status: action.status, note: action.note }),
  });
}
async function transition(jobId, status) {
  if (!connected) return setStatus("Sign in before recording a collection action.", "error");
  const driverId = $("driverId").value.trim();
  const existing = await queuedActions(driverId);
  if (existing.some(action => action.jobId === jobId)) {
    return setStatus("This stop already has a pending offline action. Sync or discard it before adding another.", "error");
  }
  const action = {
    idempotencyKey: newIdempotencyKey(),
    driverId,
    jobId,
    status,
    note: status === "completed" ? "Driver marked collection complete" : status === "exception" ? "Driver reported an exception" : null,
    createdAt: new Date().toISOString(),
  };
  if (!navigator.onLine) {
    await writeRecord("actions", action);
    setStatus("Saved " + status + " locally. It will sync when the device is online.", "ok");
    await renderQueue();
    await renderJobs(await cachedJobs(driverId));
    return;
  }
  try {
    await sendQueuedAction(action);
    setStatus("Job updated: " + status, "ok");
    await loadJobs();
  } catch (error) {
    if (!error.status || error.status >= 500 || error.status === 429) {
      await writeRecord("actions", action);
      setStatus("API could not confirm the action. It has been queued locally and will replay with the same idempotency key.", "ok");
      await renderQueue();
      await renderJobs(await cachedJobs(driverId));
    } else {
      setStatus(error.message, "error");
    }
  }
}
async function syncQueue() {
  if (syncing || !connected) return;
  if (!navigator.onLine) {
    setConnection();
    await renderQueue();
    return;
  }
  syncing = true;
  try {
    const actions = await queuedActions($("driverId").value.trim());
    for (const action of actions) {
      if (action.blocked) continue;
      try {
        await sendQueuedAction(action);
        await deleteRecord("actions", action.idempotencyKey);
      } catch (error) {
        if (error.status === 401 || error.status === 429 || !error.status || error.status >= 500) {
          setStatus("Sync paused: " + error.message + ". Pending actions remain safely stored.", "error");
          break;
        }
        action.blocked = true;
        action.lastError = error.message;
        await writeRecord("actions", action);
        setStatus("A queued action needs attention: " + error.message, "error");
        break;
      }
    }
    await renderQueue();
    const remaining = await queuedActions($("driverId").value.trim());
    if (actions.length && !remaining.length) {
      await loadJobs();
      setStatus("All queued driver actions have been confirmed by the server.", "ok");
    } else if (remaining.some(action => action.blocked)) {
      setStatus("One or more queued actions need attention. Review the queue and discard only if the server should not receive them.", "error");
    }
  } finally {
    syncing = false;
    setConnection();
    await renderQueue();
  }
}
$("login").addEventListener("submit", async event => {
  event.preventDefault();
  const driverId = $("driverId").value.trim();
  const token = $("token").value.trim();
  if (!driverId || !token) return setStatus("Driver ID and token are required.", "error");
  sessionStorage.setItem("wasteops-driver-id", driverId);
  sessionStorage.setItem("wasteops-driver-token", token);
  connected = true;
  await loadJobs();
  await syncQueue();
});
$("refresh").addEventListener("click", () => loadJobs());
$("syncPending").addEventListener("click", () => syncQueue());
$("signout").addEventListener("click", async () => {
  const driverId = $("driverId").value.trim();
  sessionStorage.removeItem("wasteops-driver-id");
  sessionStorage.removeItem("wasteops-driver-token");
  connected = false;
  $("driverId").value = "";
  $("token").value = "";
  if (driverId) await clearCachedJobs(driverId);
  $("jobs").textContent = "Signed out. Pending actions remain on this device for the same driver to sync after sign-in.";
  setStatus("Signed out.", "ok");
  await renderQueue();
});
window.addEventListener("online", () => { setConnection(); syncQueue(); });
window.addEventListener("offline", setConnection);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/driver-sw.js").catch(() => {});
$("driverId").value = sessionStorage.getItem("wasteops-driver-id") || "";
$("token").value = sessionStorage.getItem("wasteops-driver-token") || "";
connected = Boolean($("driverId").value && $("token").value);
setConnection();
renderQueue().catch(() => {});
if (connected) loadJobs().then(syncQueue);
