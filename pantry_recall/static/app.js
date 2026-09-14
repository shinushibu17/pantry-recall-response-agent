"use strict";
const $ = id => document.getElementById(id);
const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const labels = {AFFECTED:"Affected",NEEDS_EVIDENCE:"Needs evidence",NEEDS_REVIEW:"Needs review",PENDING:"Not assessed",HOLD_RECOMMENDED:"Hold recommended",REVIEW_REQUIRED:"Review required",NOT_ASSESSED:"Not assessed",AWAITING_CONFIRMATION:"Partially confirmed",COMPLETED_CONFIRMED:"Hold confirmed",PERFORM_ACTION:"Hold stock",IDENTIFY_STOCK:"Inspect stock",REVIEW_SCOPE:"Review scope",best_by_manufacturing_code:"Full printed code",product_name:"Product",package_size:"Package size",upc:"UPC",stock_group:"Group coverage",best_by_date:"Best-by date",lot_code:"Lot code"};
Object.assign(labels,{true:"Matches",false:"Mismatch",unknown:"Unknown",brand:"Brand",affected:"Known affected stock",missing_code:"Label inspection",excluded_code:"Different printed code",similar_product:"Similar product wording",mixed_codes:"Mixed donation bin",unrelated:"Different product",ambiguous_code:"Unclear transcription",contradictory_label:"Conflicting label"});
const scenarioTitles={mixed_codes:"Mixed donation bin"};
labels.mixed_codes="Mixed codes";
const label = s => labels[s] || String(s).replaceAll("_", " ").toLowerCase();
const badge = state => `<span class="badge ${escape(state)}">${escape(label(state))}</span>`;
const value = v => v == null ? '<span class="unknown-value">Not recorded</span>' : `<span class="value">${escape(typeof v === "object" ? JSON.stringify(v) : v)}</span>`;
let state, selected = "missing_code", runTimer, watchTimer, historyVersion = 0, sessionEpoch = 0, displayedRunId, displayedStatus, displayedCurrent, runGeneration = 0;
const toolSteps = [["load_recall_fixture","Load notice"],["load_inventory","Read inventory"],["compare_scope","Compare scope"],["get_case_history","Investigate cases"],["submit_briefing","Propose next checks"]];
function pipeline(report, status="READY") {
  $("tool-pipeline").innerHTML=toolSteps.map(([name,title],index)=>{const done=status==="COMPLETE" && (report?.tool_calls||[]).some(call=>(call.tool||call.name)===name);return `<div class="pipeline-step ${done?"done":""}"><span>${done?"✓":String(index+1).padStart(2,"0")}</span>${title}</div>`}).join("");
  $("agent-panel").classList.toggle("running",status==="RUNNING");
}
function overview() {
  const count=s=>state.cases.filter(c=>c.identification_state===s).length;
  const confirmed=state.cases.filter(c=>c.action_state==="COMPLETED_CONFIRMED").length;
  $("metrics").innerHTML=[[state.cases.length,"Stock groups","In your demo pantry","total"],[count("NEEDS_EVIDENCE"),"Need evidence","A label check is the next step","evidence"],[count("AFFECTED"),"Affected groups","Hold stock pending review","affected"],[confirmed,"Holds confirmed","Specified stock groups only","confirmed"]].map(([n,title,note,kind])=>`<div class="metric ${kind}"><div><span>${title}</span><strong>${n.toString().padStart(2,"0")}</strong></div><small>${note}</small></div>`).join("");
}
function message(text, success = false) { $("message").textContent = text; $("message").className = success ? "success" : ""; $("message").hidden = !text; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {cache:"no-store"} : {method:"POST",headers:{"Content-Type":"application/json","X-Pantry-Request":"reviewer"},body:JSON.stringify(body)});
  const result = await response.json();
  if (response.status === 401) showLogin();
  if (!response.ok) throw new Error(result.message || result.error || "Request failed");
  return result;
}
function showLogin() { $("login").hidden=false; $("workspace").hidden=true; $("logout").hidden=true; $("loading").hidden=true; clearTimeout(runTimer); clearTimeout(watchTimer); }
async function refresh() {
  state = await api("/api/state");
  $("loading").hidden=true; $("login").hidden=true; $("workspace").hidden=false; $("logout").hidden=state.demo_mode; $("restart").hidden=!state.demo_mode;
  $("recall-title").textContent = state.scope.variant.brand;
  const acquisition=state.source_metadata;
  $("notice-evidence").innerHTML=(acquisition?`<p class="source-dates">Company announcement: ${escape(acquisition.source_timestamps.company_announcement_date)} · FDA publication: ${escape(acquisition.source_timestamps.fda_publish_date)}<br>Notice snapshot acquired: ${escape(acquisition.notice.retrieved_at)}. Historical replay; this is not a live recall feed.</p>`:"")+["notice.product_table","notice.other_products","notice.purchase_availability"].map(source).join("");
  $("stock-count").textContent = state.cases.length;
  $("audit-count").textContent = `${state.event_count} audit events · ${state.confirmation_count} synthetic confirmations`;
  if (!state.cases.some(c=>c.inventory_id===selected)) selected=state.cases[0].inventory_id;
  overview(); renderQueue(); renderCase(); renderFollowup({latest_run_id:state.latest_run_id,followup:state.agent_followup});
  if(state.latest_run_id) await pollRun(state.latest_run_id);
  else {pipeline(null);$("agent-status").textContent="Ready to run";$("agent-status").className="";$("agent-summary").textContent="The agent checks every stock group, investigates case histories, and proposes useful next checks.";$("agent-details").hidden=true;$("agent-briefing").hidden=true;$("run-agent").disabled=false;}
  scheduleWatch();
}
function renderQueue() {
  $("stock-list").innerHTML=state.cases.map(c=>{const row=state.inventory.rows.find(r=>r.inventory_id===c.inventory_id);return `<button class="stock-button" data-id="${escape(c.inventory_id)}" aria-current="${c.inventory_id===selected}"><span class="location">${escape(row.storage_location)} · ${row.quantity} ${escape(row.unit)}</span><strong>${escape(scenarioTitles[c.inventory_id]||label(c.inventory_id))}</strong>${badge(c.identification_state)}</button>`}).join("");
  $("stock-list").querySelectorAll("button").forEach(b=>b.onclick=()=>{selected=b.dataset.id;message("");renderQueue();renderCase();});
}
function source(ref) {
  const s=state.scope.evidence[ref];
  if(s) return `<div class="source"><strong>${escape(ref)}</strong><blockquote>${escape(s.quote)}</blockquote><a href="${escape(s.source_url)}" target="_blank" rel="noreferrer">Official source ↗</a><a href="/api/source?name=${encodeURIComponent(s.source_file)}" target="_blank" rel="noreferrer">Pinned source text ↗</a><small>Span ${s.start}–${s.end} · ${escape(s.source_file)}</small><code>Source SHA-256: ${escape(s.source_sha256)}</code></div>`;
  if(state.policy.evidence[ref]) return `<div class="source"><strong>${escape(ref)} · Authored pantry policy</strong><p>${escape(state.policy.evidence[ref])}</p></div>`;
  return `<code>${escape(ref)}</code>`;
}
function renderCase() {
  const c=state.cases.find(c=>c.inventory_id===selected), row=state.inventory.rows.find(r=>r.inventory_id===selected), f=c.scope_finding;
  const tasks=c.tasks.filter(t=>t.inventory_version===c.inventory_version&&t.status!=="SUPERSEDED"), hold=tasks.find(t=>t.type==="PERFORM_ACTION"&&t.status==="OPEN");
  const refs=[...new Set([...Object.values(f.conditions).flatMap(v=>v.evidence_refs),...(f.context_evidence_refs||[])])].filter(ref=>state.scope.evidence[ref]||state.policy.evidence[ref]);
  $("case-detail").innerHTML=`<div class="card"><div class="case-top"><div><span class="eyebrow">${escape(row.storage_location)} / ${escape(c.inventory_id)}</span><h2>${escape(row.product_name)}</h2><p>${escape(row.brand)} · ${row.quantity} ${escape(row.unit)}</p></div>${badge(c.identification_state)}</div><div class="states"><div><label>Identification</label><strong>${escape(label(c.identification_state))}</strong></div><div><label>Physical action</label><strong>${escape(label(c.action_state))}</strong></div></div>${c.proposed_identification_state?'<p class="callout">Evidence supports a proposed exclusion from this recall. Reviewer acceptance is still pending; this does not authorize release.</p>':""}<dl class="facts"><div><dt>UPC</dt><dd>${value(row.upc)}</dd></div><div><dt>Package size</dt><dd>${value(row.package_size)}</dd></div><div><dt>Full printed code</dt><dd>${value(row.best_by_manufacturing_code??row.lot_code)}</dd></div><div><dt>Received</dt><dd>${value(row.received_date)}</dd></div><div><dt>Stock coverage</dt><dd>${escape(label(row.stock_group))} / ${escape(label(row.label_coverage))}</dd></div><div><dt>Evidence version</dt><dd>${escape(c.inventory_version)}</dd></div></dl></div>
  <div class="card"><div class="section-heading"><h3>Scope comparison</h3><span>Deterministic tool findings</span></div>${Object.keys(f.conditions).length?`<div class="table-wrap"><table><thead><tr><th scope="col">Condition</th><th scope="col">Stock evidence</th><th scope="col">Result</th></tr></thead><tbody>${Object.entries(f.conditions).map(([key,v])=>`<tr><td>${escape(label(key))}</td><td>${value(v.raw)}<p>Required: ${escape(typeof v.expected==="object"?JSON.stringify(v.expected):v.expected)}</p></td><td>${badge(v.truth)}<p>${escape(label(v.reason))}</p></td></tr>`).join("")}</tbody></table></div>`:'<p class="muted">This product was not selected as a candidate. No recall-specific exclusion or safety conclusion was made.</p>'}<details><summary>Source spans and policy basis</summary>${refs.map(source).join("")}<p class="muted">Inventory row SHA-256</p><code class="value">${escape(c.row_sha256)}</code><p class="muted">${escape(row.evidence_note)}</p></details></div>
  <div class="card"><h3>Next action</h3>${tasks.length?tasks.map(t=>`<div class="task"><strong>${escape(label(t.type))}</strong> ${badge(t.status)}<p>${escape(t.instruction)}</p>${t.type==="PERFORM_ACTION"?`<div class="progress"><progress max="${t.quantity}" value="${t.confirmed_quantity}"></progress><span>${t.confirmed_quantity} confirmed / ${t.remaining_quantity} ${escape(t.unit)} remaining</span></div>`:""}<p class="muted">Basis: ${escape(t.basis)} · ${escape(t.location)} · ${escape(t.task_id)}</p></div>`).join(""):'<p class="muted">No action task has been created.</p>'}<details><summary>Pantry precaution and published instructions</summary>${source("policy.hold")}${f.published_instructions.map(i=>`<div class="source"><strong>${escape(i.issuer)} · ${escape(i.audience)}</strong><p>${escape(i.action)}</p><p>When: ${escape(i.trigger)}</p>${i.evidence_refs.map(source).join("")}</div>`).join("")}<p class="muted">Confirming a hold does not record disposal or complete other recall obligations.</p></details>
  ${hold?`<details id="hold-form-section"><summary>Record a simulated hold confirmation</summary><form id="hold-form" class="form-grid"><div><label for="quantity">Quantity isolated (${escape(hold.unit)})</label><input id="quantity" name="quantity" type="number" min="1" max="${hold.remaining_quantity}" step="1" required></div><div><label for="hold-actor">Your name</label><input id="hold-actor" name="actor" maxlength="120" required autocomplete="name"></div><div class="full"><label for="hold-note">Handling note</label><textarea id="hold-note" name="note" maxlength="2000" required></textarea></div><label class="full check"><input type="checkbox" name="attest" required><span>I am recording a simulated human assertion that this quantity of this stock group was isolated at ${escape(hold.location)}.</span></label><p class="full muted">Bound to ${escape(c.inventory_version)}. Maximum ${hold.remaining_quantity} ${escape(hold.unit)}; the remainder stays open.</p><button type="submit">Record hold confirmation</button></form></details>`:""}
  <details><summary>Add or correct label evidence</summary><p class="muted">Transcribe the entire label. Preserve unknown or ambiguous values; do not fill a code from the recall notice.</p><form id="evidence-form" class="form-grid"><div class="full"><label for="code">${row.lot_code!==undefined?"Lot code":"Full top-panel BBD / manufacturing code"}</label><input id="code" name="code" value="${escape(row.best_by_manufacturing_code??row.lot_code??"")}" maxlength="200"><p class="muted">Leave empty if the code is not available.</p></div><div><label for="coverage">Labels checked</label><select id="coverage" name="coverage">${["all_units","one_unit","none"].map(v=>`<option value="${v}" ${v===row.label_coverage?"selected":""}>${escape(label(v))}</option>`).join("")}</select></div><div><label for="group">Stock group</label><select id="group" name="group">${["single_code_group","mixed_codes","unknown"].map(v=>`<option value="${v}" ${v===row.stock_group?"selected":""}>${escape(label(v))}</option>`).join("")}</select></div><div><label for="best-by">Separate best-by transcription</label><input id="best-by" name="bestBy" value="${escape(row.best_by_date??"")}" maxlength="100"></div><div><label for="evidence-actor">Your name</label><input id="evidence-actor" name="actor" maxlength="120" required autocomplete="name"></div><div class="full"><label for="evidence-note">Inspection note</label><textarea id="evidence-note" name="note" maxlength="2000" required></textarea></div><p class="full muted">Creates a new evidence version. Existing open holds may be superseded; no handling is confirmed by this entry.</p><button type="submit">Save evidence and compare</button></form></details></div>
  <div class="card"><h3>Case history</h3><div id="history" class="muted">Loading audit events…</div></div>`;
  const firstCard=$("case-detail").querySelector(".card");
  firstCard.classList.add("case-summary",c.identification_state);
  const steps=document.createElement("div"); steps.className="case-journey";
  steps.innerHTML=`<span class="done">01 · Locate stock</span><span class="${c.identification_state==="AFFECTED"?"done":""}">02 · Resolve evidence</span><span class="${c.action_state==="COMPLETED_CONFIRMED"?"done":""}">03 · Confirm hold</span>`;
  firstCard.prepend(steps);
  $("evidence-form").closest("details").id="evidence-section";
  if(state.demo_mode) {
    $("evidence-actor").value="Demo visitor";
    if($("hold-actor")) $("hold-actor").value="Demo visitor";
  }
  if(selected==="missing_code" && c.identification_state==="NEEDS_EVIDENCE") {
    const guide=document.createElement("div"); guide.className="demo-guide";
    guide.innerHTML='<div><span class="eyebrow">TRY THE INSPECTION</span><h3>Four boxes. One missing code.</h3><p>A staged label inspection is ready for Shelf A2. Fill the example, then save it to see the next action appear.</p></div><button id="fill-demo" class="secondary">Fill demo inspection ↗</button>';
    firstCard.after(guide);
    $("fill-demo").onclick=()=>{
      // Authored synthetic walkthrough input, supplied only after a visitor click.
      // It is never inferred from the notice or silently submitted as real evidence.
      $("evidence-section").open=true; $("code").value="BBD SEP 13 25 P";
      $("coverage").value="all_units"; $("group").value="single_code_group"; $("best-by").value="";
      $("evidence-actor").value="Demo visitor";
      $("evidence-note").value="Scripted demo inspection: all four synthetic Shelf A2 boxes show BBD SEP 13 25 P on their top panels. This is an authored example, not a real label observation.";
      $("evidence-form").dispatchEvent(new Event("input",{bubbles:true}));
      $("evidence-section").scrollIntoView({behavior:"smooth",block:"center"}); $("code").focus({preventScroll:true});
    };
  } else if(hold) {
    const guide=document.createElement("div"); guide.className="demo-guide hold-guide";
    guide.innerHTML=`<div><span class="eyebrow">HUMAN CONFIRMATION REQUIRED</span><h3>${hold.remaining_quantity} ${escape(hold.unit)} still need a confirmed hold.</h3><p>Try recording part of the quantity first. The remaining stock stays open.</p></div><button id="open-hold" class="secondary">Record simulated hold ↗</button>`;
    firstCard.after(guide);
    $("open-hold").onclick=()=>{$("hold-form-section").open=true;$("hold-form-section").scrollIntoView({behavior:"smooth",block:"center"});$("quantity").focus({preventScroll:true});};
  }
  const generation=++historyVersion;
  api(`/api/history?id=${encodeURIComponent(selected)}`).then(h=>{if(generation!==historyVersion)return;$("history").innerHTML=`<ol class="timeline">${h.events.slice().reverse().map(e=>`<li><strong>${escape(label(e.kind))}</strong><p>${escape(e.actor)} · ${escape(e.channel)}</p><time>${escape(new Date(e.occurred_at).toLocaleString())}</time><details><summary>Event ${e.sequence}</summary><pre>${escape(JSON.stringify(e.payload,null,2))}</pre></details></li>`).join("")}</ol>`}).catch(e=>message(e.message));
  bindForm($("evidence-form"),data=>({path:"/api/evidence",body:{inventory_id:c.inventory_id,expected_version:state.inventory.version,new_version:`web-${crypto.randomUUID()}`,actor:data.get("actor"),changes:{[row.lot_code!==undefined?"lot_code":"best_by_manufacturing_code"]:data.get("code")||null,best_by_date:data.get("bestBy")||null,label_coverage:data.get("coverage"),stock_group:data.get("group"),evidence_note:data.get("note")}}}),"Evidence saved and compared. Physical actions remain separate.");
  if(hold)bindForm($("hold-form"),data=>({path:"/api/confirm-hold",body:{confirmation_id:crypto.randomUUID(),task_id:hold.task_id,inventory_id:c.inventory_id,inventory_version:c.inventory_version,recall_version:c.recall_version,quantity:Number(data.get("quantity")),unit:hold.unit,actor:data.get("actor"),note:data.get("note"),attest_isolated:data.get("attest")==="on"}}),"Synthetic hold confirmation recorded. Only the specified quantity was applied.");
}
function bindForm(form,command,success) {
  let pending;
  form.addEventListener("input",()=>pending=undefined);
  form.onsubmit=async event=>{event.preventDefault();const button=form.querySelector("button[type=submit]");button.disabled=true;
    try{pending ||= command(new FormData(form));await api(pending.path,pending.body);await refresh();message(success,true)}catch(e){message(e.message)}finally{button.disabled=false}};
}
async function pollRun(id) {
  clearTimeout(runTimer);
  const epoch=sessionEpoch, generation=++runGeneration;
  const run=await api(`/api/agent/${encodeURIComponent(id)}`), report=run.report;
  if(epoch!==sessionEpoch || generation!==runGeneration)return;
  displayedRunId=id; displayedStatus=run.status; displayedCurrent=run.current;
  pipeline(report,run.current?run.status:"STALE");
  renderBriefing(run);
  $("run-agent").disabled=run.status==="RUNNING";
  $("restart").disabled=run.status==="RUNNING";
  $("agent-status").className=run.current?run.status:"stale";
  $("agent-status").textContent=`${run.status}${!run.current?" · earlier workflow snapshot":""}`;
  $("agent-summary").textContent=report?`${report.validated_results?.length||0} stock comparisons · ${report.tool_calls?.length||0} tool calls · ${report.model_calls||0} model calls · 0 human actions confirmed by the agent. ${!run.current?"Evidence or events have changed. A new briefing is needed; check follow-up status below.":run.status!=="COMPLETE"?"Evaluation did not complete; advisory prose is withheld.":!report.investigation_mode?"Earlier baseline run. Recheck pantry to create agent-selected next checks.":"All required tools and stock comparisons completed."}`:run.status==="RUNNING"?"The agent is loading evidence and calling the comparison tools. You can continue reviewing stock.":"The previous run was interrupted. Start a new run; no human action was confirmed.";
  $("agent-details").hidden=!report;
  if(report)$("agent-content").innerHTML=`<pre>${escape((report.tool_calls||[]).map((t,i)=>`${i+1}. ${t.name||t.tool||JSON.stringify(t)} ${JSON.stringify(t.arguments||{})}`).join("\n"))}</pre>${report.agent_explanation_unverified?`<p class="muted">Advisory model explanation. Use the deterministic findings and source evidence for decisions.</p><pre>${escape(report.agent_explanation_unverified)}</pre>`:""}`;
  scheduleWatch();
}
$("login-form").onsubmit=async e=>{e.preventDefault();try{await api("/api/login",{password:$("password").value});$("password").value="";message("");await refresh()}catch(e){message(e.message)}};
$("logout").onclick=async()=>{try{await api("/api/logout",{});showLogin()}catch(e){message(e.message)}};
let agentRequest;
$("restart").onclick=async()=>{try{clearTimeout(runTimer);clearTimeout(watchTimer);sessionEpoch++;displayedRunId=undefined;await api("/api/session",{});selected="missing_code";agentRequest=undefined;await refresh();message("A fresh demo pantry is ready. Your previous replay remains in the audit store.",true)}catch(e){message(e.message)}};
$("run-agent").onclick=async()=>{ $("run-agent").disabled=true;try{agentRequest ||= crypto.randomUUID();const run=await api("/api/agent",{request_id:agentRequest});agentRequest=undefined;message("");await refresh()}catch(e){message(e.message);$("run-agent").disabled=false}};
refresh().catch(e=>{if(!$("login").hidden)message("");else{$("loading").textContent="Unable to load the workspace.";message(e.message)}});


function renderFollowup(status) {
  state.agent_followup=status.followup || {enabled:false,pending:false};
  const follow=state.agent_followup;
  $("follow-toggle").hidden=!status.latest_run_id;
  $("follow-toggle").textContent=follow.enabled?"Pause follow-ups":"Resume follow-ups";
  $("run-agent").textContent=status.latest_run_id?"Recheck pantry":"Start recall agent";
  $("follow-up-note").textContent=follow.notice || (follow.enabled
    ? follow.pending?"An accepted update is queued for the agent. Your evidence and receipts are already saved."
      :"Following your updates. New label evidence and hold receipts trigger a briefing, within the shared daily allowance."
    :status.latest_run_id?"Automatic follow-ups are paused. Your evidence workflow still works."
      :"Start the agent to investigate the pantry and follow your updates. Live Bedrock runs share a 20-per-day allowance.");
}
function scheduleWatch() {
  clearTimeout(watchTimer);
  if(!$("workspace").hidden && (state?.agent_followup?.enabled || displayedStatus==="RUNNING"))
    watchTimer=setTimeout(watchAgent,2500);
}
async function watchAgent() {
  const epoch=sessionEpoch;
  try {
    const status=await api("/api/agent-status");
    if(epoch!==sessionEpoch)return;
    renderFollowup(status);
    if(status.event_count!==undefined && state.event_count!==status.event_count) {await refresh();return;}
    if(status.latest_run_id && (status.latest_run_id!==displayedRunId || status.status!==displayedStatus || status.status==="RUNNING"))
      await pollRun(status.latest_run_id);
  } catch(e) { if(epoch===sessionEpoch)message(e.message); }
  finally { if(epoch===sessionEpoch)scheduleWatch(); }
}
function renderBriefing(run) {
  const brief=run.current && run.status==="COMPLETE" ? run.report?.briefing : null;
  $("agent-briefing").hidden=!brief;
  if(!brief)return;
  const changes=brief.changes.map(change=>{
    const row=state.inventory.rows.find(r=>r.inventory_id===change.inventory_id);
    const title=escape(row?.storage_location || change.inventory_id);
    if(change.kind==="HOLD_CONFIRMED")return `<li><strong>${title}: human hold receipt</strong><span>${change.evidence.confirmed_quantity} ${escape(change.evidence.unit)} confirmed; ${change.evidence.remaining_quantity} remaining. Event ${change.event_sequence}.</span></li>`;
    return `<li><strong>${title}: label evidence updated</strong><span>${Object.entries(change.field_changes||{}).filter(([field])=>field!=="evidence_note").map(([field,delta])=>`${escape(label(field))}: ${value(delta.before)} &rarr; ${value(delta.after)}`).join("; ")} &middot; Event ${change.event_sequence}</span></li>`;
  }).join("");
  $("agent-briefing").innerHTML=`<div class="briefing-heading"><div><span class="eyebrow">${brief.trigger==="workflow_change"?"TRIGGERED BY YOUR UPDATE":"AGENT INVESTIGATION"}</span><h3>Suggested next checks</h3></div><span>${brief.priorities.length} proposed &middot; ${brief.open_tasks_total} tasks remain open</span></div>${changes?`<ul class="change-list">${changes}</ul>`:""}<div class="priority-grid">${brief.priorities.map((priority,i)=>{
    const task=priority.task, amount=task.type==="PERFORM_ACTION"?task.remaining_quantity:task.quantity;
    return `<article class="priority-card"><span class="priority-number">0${i+1}</span><span class="eyebrow">${escape(task.location)}</span><h4>${escape(label(task.type))}</h4><p class="priority-stock">${amount} ${escape(task.unit)} &middot; ${escape(label(task.identification_state))}</p><p>${escape(task.instruction)}</p><p class="priority-reason"><strong>Agent rationale (advisory)</strong>${escape(priority.rationale_advisory)}</p><button class="secondary" data-open-case="${escape(task.inventory_id)}">Open stock group</button><details><summary>Task evidence</summary>${(priority.cited_evidence_ids||[priority.cited_evidence_id]).map(source).join("")}<small>Inventory version: ${escape(task.inventory_version)}<br>Task: ${escape(task.task_id)}</small></details></article>`;
  }).join("")}</div><p class="briefing-limit">Task IDs, open status, quantities and cited evidence are checked by the application. The agent chooses the order and rationale; this is not a food-safety risk ranking. ${brief.unselected_open_tasks} other open tasks remain in the stock list.</p>`;
  $("agent-briefing").querySelectorAll("[data-open-case]").forEach(button=>button.onclick=()=>{selected=button.dataset.openCase;renderQueue();renderCase();$("case-detail").scrollIntoView({behavior:"smooth",block:"start"});});
}
$("follow-toggle").onclick=async()=>{
  try {const status=await api("/api/follow-up",{enabled:!state.agent_followup.enabled});renderFollowup(status);await refresh();}
  catch(e) {message(e.message);}
};
