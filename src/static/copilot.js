"use strict";
const $ = id => document.getElementById(id);
const labels = {generated:"Suggested response · verify before use",generation_not_configured:"Generation service not configured",generation_failed:"Generation unavailable",no_evidence:"No retrieval candidates",context_unavailable:"Context budget unavailable",service_unavailable:"Retrieval unavailable",invalid_request:"Check your question"};
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function officialLink(url, label, className) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" || parsed.hostname !== "support.apple.com" || parsed.username || parsed.password || parsed.port) throw new Error("Invalid source");
    const a = element("a", className, label); a.href = parsed.href; a.target = "_blank"; a.rel = "noopener noreferrer"; return a;
  } catch (_) { return element("span", className, "Source link unavailable"); }
}
function renderResult(result) {
  $("request-status").textContent = labels[result.status] || "Request status";
  $("result-message").textContent = result.message || "The request could not be completed.";
  if (result.repair_commands) $("result-message").textContent += "\n" + result.repair_commands.join("\n");
  $("answer").textContent = result.answer || ""; $("answer").hidden = !result.answer;
  $("sources-list").replaceChildren();
  const sources = Array.isArray(result.sources) ? result.sources : [];
  $("sources-empty").hidden = sources.length > 0;
  sources.forEach(source => $("sources-list").appendChild(officialLink(source.source_url, `[${source.citation_id}] ${source.title} · ${source.heading}`, "source-link")));
  const evidence = Array.isArray(result.evidence) ? result.evidence : [];
  $("evidence-count").textContent = String(evidence.length); $("evidence-list").replaceChildren();
  if (!evidence.length) $("evidence-list").appendChild(element("p", "empty-evidence", "No evidence available for this request."));
  evidence.forEach(item => {
    const card = element("details", "evidence-card");
    const summary = element("summary");
    summary.appendChild(element("span", "evidence-title", `${item.rank}. ${item.title}`));
    const context = item.used_for_generation ? ` · Sent as context [${item.citation_id}]` : " · Retrieved candidate";
    summary.appendChild(element("span", "evidence-meta", `Similarity ${Number(item.score).toFixed(3)}${context}`));
    summary.appendChild(element("span", "evidence-meta", item.heading));
    card.appendChild(summary);
    card.appendChild(element("div", "evidence-body", (item.context_text ? item.context_text + "\n\n" : "") + item.text));
    card.appendChild(officialLink(item.source_url, "Open official Apple Support article ↗", "evidence-url"));
    card.appendChild(element("div", "evidence-id", `${item.chunk_id}\n${item.doc_id} · Characters ${item.start_char}–${item.end_char}\nBody SHA-256 ${item.content_sha256}`));
    $("evidence-list").appendChild(card);
  });
}
$("question").addEventListener("input", () => { $("character-count").textContent = `${$("question").value.length} / 2000`; });
document.querySelectorAll("[data-question]").forEach(button => button.addEventListener("click", () => {
  $("question").value = button.dataset.question; $("question").dispatchEvent(new Event("input")); $("question").focus();
}));
$("question-form").addEventListener("submit", async event => {
  event.preventDefault();
  const question = $("question").value.trim(); if (!question) return;
  $("submit-button").disabled = true; $("submit-button").textContent = "Searching…";
  $("response-panel").setAttribute("aria-busy", "true");
  renderResult({status:"loading",message:"Searching the reviewed local evidence…",sources:[],evidence:[]});
  $("request-status").textContent = "Working…";
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 70000);
  try {
    const reply = await fetch("/api/chat", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question}),signal:controller.signal});
    const data = await reply.json(); renderResult(data);
  } catch (_) {
    renderResult({status:"service_unavailable",message:"The backend did not return a response. Check the local service and retry.",sources:[],evidence:[]});
  } finally {
    clearTimeout(timer); $("submit-button").disabled = false; $("submit-button").textContent = "Search evidence ↗";
    $("response-panel").setAttribute("aria-busy", "false");
  }
});
fetch("/api/status").then(reply => reply.json()).then(status => {
  const ready = status.retrieval === "ready";
  $("resource-status").textContent = ready ? `${status.documents} local support articles · Local evidence ready` : "Local evidence unavailable";
  $("service-banner").textContent = ready ? status.generation.message : status.startup_error.message + "\n" + status.startup_error.commands.join("\n");
  $("service-banner").classList.toggle("error", !ready);
}).catch(() => { $("service-banner").textContent = "Cannot reach the backend. Check the local service."; $("resource-status").textContent = "Backend unavailable"; });
