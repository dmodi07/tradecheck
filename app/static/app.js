"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const form = $("#search"), input = $("#q"), go = $("#go"), msg = $("#q-msg");
const result = $("#result"), guide = $("#guide"), coverage = $("#coverage");
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const wait = ms => new Promise(r => setTimeout(r, reducedMotion() ? 0 : ms));

/* ---------- Vocabulary ---------- */

const LIST_NAMES = {
  "OFAC-SDN":  "US Treasury: Specially Designated Nationals list",
  "OFAC-CONS": "US Treasury: other sanctions lists",
  "CA-SEMA":   "Government of Canada: autonomous sanctions list",
};
const listName = id => LIST_NAMES[id] || id;
const country = id => id.startsWith("CA-") ? "Canada" : "United States";

const OUTCOME = {
  Avoid: {
    cls: "is-listed", stamp: "Listed",
    headline: "This name is on a sanctions list",
    answer: n => `${n === 1 ? "One listed party has" : n + " listed parties have"} this name. Trading with a sanctioned party can be illegal in Canada and the US.`,
    steps: [
      "Don’t sign, pay or ship anything to this party for now.",
      "Compare the details below with what you know about your partner: country, date of birth, registration numbers. Same name doesn’t always mean same party.",
      "If the details line up, or you can’t tell, talk to a trade lawyer or contact Global Affairs Canada before going further.",
    ],
  },
  Caution: {
    cls: "is-review", stamp: "Review",
    headline: "A similar name is on a sanctions list",
    answer: n => `${n === 1 ? "One listed party has" : n + " listed parties have"} a name close to this one. That’s common with shared or transliterated names, and it isn’t a match yet.`,
    steps: [
      "Compare the details below with your partner’s: country, date of birth, registration or tax numbers.",
      "If anything is missing, ask your partner for their business registration documents.",
      "If you can’t rule a listing out, treat it as a match and get advice before you proceed.",
    ],
  },
  Clear: {
    cls: "is-nomatch", stamp: "No match",
    headline: "No match on the lists we checked",
    answer: () => "This name doesn’t appear on any of the lists below, as of the dates shown.",
    steps: [
      "Keep this record with the deal’s paperwork. It shows you checked, when, and against what.",
      "Check again before each new order or contract. Lists change, sometimes daily.",
      "Make sure the spelling matches your partner’s registration documents, and try any other names they trade under.",
    ],
  },
  Unknown: {
    cls: "is-unchecked", stamp: "Not checked",
    headline: "This name couldn’t be checked",
    answer: () => "The sanctions lists aren’t loaded, so there’s nothing to compare against. This is not a pass.",
    steps: [
      "Don’t treat this as clear.",
      "Ask whoever runs TradeCheck to download and load the lists, then check the name again.",
    ],
  },
  // Lists are loaded but the name reduced to nothing comparable.
  UnreadableName: {
    cls: "is-unchecked", stamp: "Not checked",
    headline: "This name couldn’t be checked",
    answer: () => "The lists are loaded, but this name has nothing we can compare. Names are matched in Latin letters, the way they appear on most trade and registration documents.",
    steps: [
      "Don’t treat this as clear.",
      "Type the name in Latin letters, as it appears on your partner’s registration or shipping documents, and check again.",
    ],
  },
};

// OFAC program codes, in plain words. Matched on the code's prefix.
const PROGRAMS = [
  [/^(RUSSIA|CAATSA - RUSSIA|PEESA|UKRAINE)/, "Russia-related sanctions"],
  [/^BELARUS/, "Belarus-related sanctions"],
  [/^(IRAN|IRGC|IFSR|IFCA|HRIT-IR|CAATSA - IRAN|PAARSSR)/, "Iran-related sanctions"],
  [/^(SDGT|FTO)/, "Terrorism"],
  [/^(SDNTK|SDNT|ILLICIT-DRUGS)/, "Drug trafficking"],
  [/^TCO/, "Organized crime"],
  [/^NPWMD/, "Weapons of mass destruction"],
  [/^CYBER/, "Malicious cyber activity"],
  [/^(GLOMAG|MAGNIT)/, "Corruption or human-rights abuse"],
  [/^ELECTION/, "Election interference"],
  [/^HOSTAGES/, "Hostage-taking"],
  [/^DPRK/, "North Korea-related sanctions"],
  [/^CUBA/, "Cuba-related sanctions"],
  [/^VENEZUELA/, "Venezuela-related sanctions"],
  [/^(SYRIA|HRIT-SY)/, "Syria-related sanctions"],
  [/^BURMA/, "Myanmar-related sanctions"],
  [/^DRCONGO/, "Democratic Republic of the Congo-related sanctions"],
  [/^CAR$/, "Central African Republic-related sanctions"],
  [/^(SUDAN|DARFUR)/, "Sudan-related sanctions"],
  [/^SOUTH SUDAN/, "South Sudan-related sanctions"],
  [/^SOMALIA/, "Somalia-related sanctions"],
  [/^YEMEN/, "Yemen-related sanctions"],
  [/^LIBYA/, "Libya-related sanctions"],
  [/^IRAQ/, "Iraq-related sanctions"],
  [/^LEBANON/, "Lebanon-related sanctions"],
  [/^NICARAGUA/, "Nicaragua-related sanctions"],
  [/^BALKANS/, "Western Balkans-related sanctions"],
  [/^CMIC/, "Chinese military companies"],
  [/^HKAA/, "Hong Kong-related sanctions"],
  [/^ICC/, "International Criminal Court-related sanctions"],
];

function reasons(entity) {
  const p = entity.program || "";
  if (entity.source_list.startsWith("CA-")) {
    const regime = p.split(" / ")[0].trim();
    if (!regime) return "Sanctions";
    if (/^Justice for Victims/.test(regime)) return "Corruption or human-rights abuse";
    if (/Hamas|Settler/.test(regime)) return regime;
    return `${regime}-related sanctions`;
  }
  const out = [];
  for (const code of p.split(/[;,]\s*/).map(s => s.trim()).filter(Boolean)) {
    const hit = PROGRAMS.find(([re]) => re.test(code));
    const label = hit ? hit[1] : code;
    if (!out.includes(label)) out.push(label);
  }
  return out.join(", ") || "US sanctions";
}

function howMatched(h) {
  if (h.match_type === "exact") {
    if (h.quality === "primary") return "Exact match to the listed name";
    if (h.quality === "weak") return "Matches a loosely documented alias";
    return "Exact match to a known alias";
  }
  if (h.match_type === "partial") return "Matches part of the listed name";
  return `Similar spelling (${Math.round(h.score)}% alike)`;
}

const KIND = { individual: "Person", entity: "Organization", vessel: "Ship" };

const fmtDate = iso => {
  const d = new Date(iso);
  return isNaN(d) ? (iso || "unknown date") : d.toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" });
};
const fmtDay = iso => {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString("en-CA", { dateStyle: "medium" });
};

/* ---------- DOM helpers ---------- */

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) n.append(k);
  return n;
}

function icon(id, size = 16) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", size); svg.setAttribute("height", size);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${id}`);
  svg.append(use);
  return svg;
}

/* ---------- Validation ---------- */

const HINT = "Use the name as it appears on their registration or shipping documents.";
const LATIN = /[A-Za-zÀ-ɏ]/;
const LETTER = /\p{L}/u;

function validate(raw) {
  const name = raw.trim();
  if (!name) return "Enter the name of a company or person to check.";
  if (name.length < 2) return "Enter at least 2 characters.";
  if (name.length > 200) return `That’s ${name.length} characters. Names need to be under 200.`;
  if (!LETTER.test(name)) return "Names need letters. Check for a typo.";
  if (!LATIN.test(name)) return "Type the name in Latin letters, as on their registration documents. Other scripts can’t be matched yet.";
  return null;
}

let showedError = false;

function setMessage(text, kind = "hint") {
  msg.replaceChildren();
  msg.classList.toggle("is-error", kind === "error");
  if (kind !== "hint") msg.append(icon(kind === "error" ? "i-alert" : "i-info"));
  msg.append(el("span", { text }));
  input.setAttribute("aria-invalid", kind === "error" ? "true" : "false");
}

function rejectInput(text) {
  setMessage(text, "error");
  showedError = true;
  input.classList.remove("shake");
  void input.offsetWidth; // restart the animation
  input.classList.add("shake");
  input.focus();
}

input.addEventListener("animationend", () => input.classList.remove("shake"));
input.addEventListener("input", () => {
  const error = validate(input.value);
  if (showedError && error && input.value.trim()) { setMessage(error, "error"); return; }
  showedError = false;
  const v = input.value.trim();
  if (v && LETTER.test(v) && !LATIN.test(v)) setMessage("Names are matched in Latin letters. Try the spelling on their registration documents.", "info");
  else setMessage(HINT);
});

/* ---------- Results ---------- */

function detailRows(e) {
  const rows = [["Type", KIND[e.entity_type] || e.entity_type]];
  if (e.dobs?.length) rows.push([e.entity_type === "vessel" ? "Built" : "Born", e.dobs.join("; ")]);
  if (e.place_of_birth) rows.push(["Place of birth", e.place_of_birth]);
  if (e.countries?.length) rows.push(["Country", e.countries.join(", ")]);
  for (const id of (e.ids || []).slice(0, 4)) {
    if (!id.value) continue;
    rows.push([(id.type || "ID").replace(/[\s:-]+$/, ""), id.value + (id.country ? ` (${id.country})` : "")]);
  }
  if (e.listed_date) rows.push(["Listed since", e.listed_date]);
  return rows;
}

// One party can appear on several lists (e.g. US and Canada). Show it once with
// every list that names it. Same party only if: same name and type, a different
// list, and no conflicting birth years.
function groupHits(hits) {
  const groups = [];
  const nameKey = e => `${e.entity_type}|${e.primary_name.toLowerCase().replace(/\s+/g, " ").trim()}`;
  const years = e => new Set((e.dobs || []).flatMap(d => d.match(/\b(1[89]|20)\d\d\b/g) || []));
  const sameParty = (g, e) => {
    if (nameKey(g.entity) !== nameKey(e)) return false;
    if (g.sources.some(s => s.source_list === e.source_list)) return false;
    const a = years(g.entity), b = years(e);
    return !a.size || !b.size || [...a].some(y => b.has(y));
  };
  for (const h of hits) {
    const g = groups.find(g => sameParty(g, h.entity));
    if (!g) { groups.push({ ...h, sources: [h.entity] }); continue; }
    g.sources.push(h.entity);
    if (h.level === "avoid" && g.level !== "avoid") {
      Object.assign(g, { level: h.level, score: h.score, match_type: h.match_type, quality: h.quality, matched_name: h.matched_name });
    }
    if (detailRows(h.entity).length > detailRows(g.entity).length) g.entity = h.entity;
  }
  return groups;
}

function renderListing(h) {
  const e = h.entity;
  const byCountry = new Map();
  for (const src of h.sources) {
    const c = country(src.source_list), r = reasons(src);
    if (!byCountry.has(c)) byCountry.set(c, []);
    if (!byCountry.get(c).includes(r)) byCountry.get(c).push(r);
  }
  const why = [...byCountry].map(([c, rs]) => `${c}: ${rs.join(", ")}`).join(". ");
  const strong = h.level === "avoid";
  const dl = el("dl");
  for (const [k, v] of detailRows(e)) dl.append(el("dt", { text: k }), el("dd", { text: v }));
  return el("article", { class: `listing ${strong ? "is-listed" : "is-review"}` },
    el("div", { class: "listing__top" },
      el("h4", { class: "listing__name", text: e.primary_name, style: "margin:0" }),
      el("span", { class: "badge", text: strong ? "Strong match" : "Possible match" })),
    el("p", { class: "listing__why" }, `${why}. `,
      el("span", { class: "listing__how", text: howMatched(h) + (h.matched_name !== e.primary_name ? `: “${h.matched_name}”.` : ".") })),
    dl,
    el("p", { class: "listing__sources" }, "Official source: ",
      ...h.sources.flatMap((src, i) => [i ? ", " : null,
        el("a", { href: src.source_url, target: "_blank", rel: "noopener", text: listName(src.source_list) })])));
}

const SHOWN = 5;

function checklistItem(label, when, state) {
  const tick = el("span", { class: `tick ${state ? "is-" + state : ""}`, "aria-hidden": "true" }, icon("i-check", 12));
  return el("li", {}, tick, el("span", { text: label }), el("span", { class: "when", text: when }));
}

function render(res) {
  const unreadable = res.verdict === "Unknown" && (res.lists_screened || []).length > 0;
  const o = unreadable ? OUTCOME.UnreadableName : (OUTCOME[res.verdict] || OUTCOME.Unknown);
  const node = $("#tpl-record").content.firstElementChild.cloneNode(true);
  const f = name => node.querySelector(`[data-f="${name}"]`);
  const hits = groupHits(res.hits || []);

  node.classList.add(o.cls);
  f("query").textContent = res.query;
  f("headline").textContent = o.headline;
  f("answer").textContent = o.answer(hits.length);
  f("stamp").textContent = o.stamp;
  for (const s of o.steps) f("steps").append(el("li", { text: s }));

  if (hits.length) {
    f("matches-section").hidden = false;
    f("matches-title").textContent = hits.length === 1 ? "The listing we found" : `The ${hits.length} listings we found`;
    f("matches-intro").textContent = "Compare these details with your partner’s. A match needs more than a shared name.";
    const box = f("matches");
    hits.forEach((h, i) => {
      const item = renderListing(h);
      if (i >= SHOWN) item.hidden = true;
      box.append(item);
    });
    if (hits.length > SHOWN) {
      const more = el("button", { class: "btn btn--text", type: "button", "data-more": "",
                                  "aria-expanded": "false", text: `Show all ${hits.length} listings` });
      more.addEventListener("click", () => {
        const hidden = [...box.querySelectorAll(".listing[hidden]")];
        hidden.forEach((item, i) => { item.style.setProperty("--i", i); item.classList.add("is-revealed"); item.hidden = false; });
        more.remove();
        hidden[0]?.querySelector(".listing__name")?.setAttribute("tabindex", "-1");
        hidden[0]?.querySelector(".listing__name")?.focus({ preventScroll: true });
      });
      box.append(more);
    }
  }

  const lists = res.lists_screened || [];
  if (lists.length) {
    for (const l of lists) f("lists").append(checklistItem(listName(l.source_list), `Updated ${fmtDate(l.fetched_at)}`, "done"));
  } else {
    f("lists").append(el("li", {}, el("span"), el("span", { text: "No lists were available." })));
  }
  f("fine").replaceChildren(`Checked on ${fmtDate(res.checked_at)}`, el("br"), res.disclaimer || "Not legal advice.");

  node.querySelector('[data-action="print"]').addEventListener("click", () => window.print());
  node.querySelector('[data-action="again"]').addEventListener("click", startOver);
  return node;
}

function startOver() {
  input.value = "";
  setMessage(HINT);
  window.scrollTo({ top: 0, behavior: reducedMotion() ? "auto" : "smooth" });
  input.focus({ preventScroll: true });
}

function renderError(title, body) {
  const retry = el("button", { class: "btn", type: "button", text: "Try again" });
  retry.addEventListener("click", () => form.requestSubmit());
  return el("div", { class: "alert", role: "alert" }, icon("i-alert", 20),
    el("div", {}, el("h2", { text: title }), el("p", { text: body }), retry));
}

/* ---------- The check ---------- */

let knownLists = [];   // from /status, used to show progress before the answer arrives
let inFlight = null;

function setBusy(busy) {
  go.disabled = busy;
  go.setAttribute("aria-busy", String(busy));
  go.querySelector(".spinner").hidden = !busy;
  go.querySelector("[data-label]").textContent = busy ? "Checking…" : "Check name";
}

// While the request runs, show the lists being checked; tick each one off as the answer lands.
function progressCard(name) {
  const items = (knownLists.length ? knownLists : [{ source_list: "…" }])
    .map(l => checklistItem(knownLists.length ? listName(l.source_list) : "Sanctions lists", "", "pending"));
  return el("article", { class: "record", "aria-busy": "true" },
    el("section", { class: "record__section", style: "border-top:0" },
      el("h3", { text: `Checking “${name}”` }),
      el("ul", { class: "checklist" }, ...items)));
}

async function check(name) {
  inFlight?.abort();
  const ctrl = inFlight = new AbortController();
  setBusy(true);
  guide.hidden = true;
  const card = progressCard(name);
  result.replaceChildren(card);
  result.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
  const started = performance.now();

  try {
    const r = await fetch("/screen", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }), signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`The server answered with an error (${r.status}).`);
    const data = await r.json();

    // Tick each list off, then hand over to the record. Kept short: under a second.
    const ticks = [...card.querySelectorAll(".tick")];
    await wait(Math.max(0, 250 - (performance.now() - started)));
    for (const t of ticks) { t.classList.replace("is-pending", "is-done"); await wait(130); }
    await wait(180);
    if (ctrl !== inFlight) return;

    const record = render(data);
    result.replaceChildren(record);
    record.focus({ preventScroll: true });
  } catch (err) {
    if (err.name === "AbortError") return;
    const why = err.message.startsWith("The server") ? err.message : "TradeCheck couldn’t reach its server.";
    result.replaceChildren(renderError("The check didn’t run",
      `${why} Make sure it’s running, then try again. Nothing was screened, so don’t treat this as a pass.`));
  } finally {
    if (ctrl === inFlight) { setBusy(false); inFlight = null; }
  }
}

form.addEventListener("submit", e => {
  e.preventDefault();
  const error = validate(input.value);
  if (error) { rejectInput(error); return; }
  showedError = false;
  setMessage(HINT);
  check(input.value.trim());
});

document.querySelectorAll("[data-example]").forEach(b => b.addEventListener("click", () => {
  input.value = b.dataset.example;
  setMessage(HINT);
  showedError = false;
  check(b.dataset.example);
}));

(async function loadCoverage() {
  try {
    const r = await fetch("/status");
    if (!r.ok) throw new Error();
    const { lists } = await r.json();
    knownLists = lists;
    if (!lists.length) {
      coverage.classList.add("is-down");
      coverage.textContent = "The sanctions lists aren’t loaded yet, so checks will come back as Not checked.";
      return;
    }
    const total = lists.reduce((a, l) => a + l.entries, 0).toLocaleString("en-CA");
    const newest = lists.map(l => l.fetched_at).sort().pop();
    coverage.classList.add("is-live");
    coverage.textContent = `Checks ${total} listed people, organizations and ships across ${lists.length} government lists, last downloaded ${fmtDay(newest)}.`;
  } catch {
    coverage.classList.add("is-down");
    coverage.textContent = "Couldn’t reach the TradeCheck server. Make sure it’s running.";
  }
})();
