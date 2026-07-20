/* app.js — v1.0.0
 * Client-side only: fetches data/postings.json (same path GitHub Pages
 * serves this file from) and renders/filters/sorts entirely in-browser.
 */

const SOURCE_LABELS = {
  iloilo_city: "Iloilo City",
  iloilo_province: "Iloilo Province",
  guimaras: "Guimaras",
};

const CATEGORY_CLASS = {
  "Construction/Infrastructure": "cat-construction",
  "Goods & Supplies": "cat-goods",
  "IT/Technology": "cat-it",
  "Consulting/Professional Services": "cat-consulting",
  "Other": "cat-other",
};

const DAY_MS = 24 * 60 * 60 * 1000;

let ALL_POSTINGS = [];

function computeStatus(posting, now) {
  const closing = posting.closing_date ? new Date(posting.closing_date + "T00:00:00") : null;
  if (closing && closing.getTime() < now.getTime()) return "closed";
  if (closing) {
    const daysToClose = (closing.getTime() - now.getTime()) / DAY_MS;
    if (daysToClose <= 7) return "closing";
  }
  const posted = posting.date_posted ? new Date(posting.date_posted + "T00:00:00") : null;
  if (posted) {
    const daysSincePosted = (now.getTime() - posted.getTime()) / DAY_MS;
    if (daysSincePosted <= 3 && daysSincePosted >= -1) return "new";
  }
  return "normal";
}

const STATUS_LABEL = { new: "New", closing: "Closing Soon", closed: "Closed", normal: "Normal" };

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function renderCard(posting, now) {
  const status = computeStatus(posting, now);
  const catClass = CATEGORY_CLASS[posting.category_tag] || "cat-other";
  const sourceLabel = SOURCE_LABELS[posting.source] || posting.source;

  const closingHtml = posting.closing_date
    ? `<span><span class="label">Closes</span>${escapeHtml(formatDate(posting.closing_date))}</span>`
    : "";

  const docLinkHtml = posting.doc_url
    ? `<a href="${escapeHtml(posting.doc_url)}" target="_blank" rel="noopener">Document</a>`
    : "";

  return `
    <article class="card" data-status="${status}">
      <div class="card-top">
        <div class="badges">
          <span class="badge source">${escapeHtml(sourceLabel)}</span>
          <span class="badge ${catClass}">${escapeHtml(posting.category_tag || "Other")}</span>
        </div>
        <span class="status-pill ${status}">${STATUS_LABEL[status]}</span>
      </div>
      <h3 class="card-title">${escapeHtml(posting.title)}</h3>
      <div class="card-meta">
        ${posting.ref_no ? `<span class="ref">${escapeHtml(posting.ref_no)}</span>` : ""}
        ${posting.category ? `<span>${escapeHtml(posting.category)}</span>` : ""}
      </div>
      <div class="card-dates">
        <span><span class="label">Posted</span>${escapeHtml(formatDate(posting.date_posted))}</span>
        ${closingHtml}
      </div>
      <div class="card-links">
        <a class="primary" href="${escapeHtml(posting.url)}" target="_blank" rel="noopener">Source</a>
        ${docLinkHtml}
      </div>
    </article>
  `;
}

function applyFilters() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  const sourceFilter = document.getElementById("filter-source").value;
  const categoryFilter = document.getElementById("filter-category").value;
  const statusFilter = document.getElementById("filter-status").value;
  const sortOrder = document.getElementById("sort-order").value;
  const now = new Date();

  let filtered = ALL_POSTINGS.filter((p) => {
    if (sourceFilter && p.source !== sourceFilter) return false;
    if (categoryFilter && p.category_tag !== categoryFilter) return false;
    if (statusFilter && computeStatus(p, now) !== statusFilter) return false;
    if (q) {
      const haystack = `${p.title || ""} ${p.ref_no || ""}`.toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    if (sortOrder === "date_asc") {
      return (a.date_posted || "").localeCompare(b.date_posted || "");
    }
    if (sortOrder === "closing_asc") {
      const ca = a.closing_date || "9999-99-99";
      const cb = b.closing_date || "9999-99-99";
      return ca.localeCompare(cb);
    }
    return (b.date_posted || "").localeCompare(a.date_posted || "");
  });

  const grid = document.getElementById("grid");
  const empty = document.getElementById("empty");
  document.getElementById("result-count").textContent = `${filtered.length} of ${ALL_POSTINGS.length} postings`;

  if (filtered.length === 0) {
    grid.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  grid.innerHTML = filtered.map((p) => renderCard(p, now)).join("");
}

function updateHeaderStats() {
  const now = new Date();
  const total = ALL_POSTINGS.length;
  const newCount = ALL_POSTINGS.filter((p) => computeStatus(p, now) === "new").length;
  const closingCount = ALL_POSTINGS.filter((p) => computeStatus(p, now) === "closing").length;
  document.getElementById("stat-total").textContent = total;
  document.getElementById("stat-new").textContent = newCount;
  document.getElementById("stat-closing").textContent = closingCount;
}

async function init() {
  try {
    const resp = await fetch("data/postings.json", { cache: "no-store" });
    ALL_POSTINGS = await resp.json();
  } catch (e) {
    document.getElementById("grid").innerHTML = "";
    document.getElementById("empty").style.display = "block";
    document.querySelector("#empty .big").textContent = "Could not load postings data";
    return;
  }

  updateHeaderStats();
  applyFilters();

  ["search", "filter-source", "filter-category", "filter-status", "sort-order"].forEach((id) => {
    document.getElementById(id).addEventListener("input", applyFilters);
    document.getElementById(id).addEventListener("change", applyFilters);
  });
}

init();
