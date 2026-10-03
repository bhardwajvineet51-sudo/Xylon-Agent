import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, STATUSES, label, date } from "../api";

const TABS = ["Overview", "Research", "Website Audit", "Opportunities", "Contacts", "Outreach", "Activity"];
const Src = ({ url }) => <a href={url} target="_blank" rel="noopener noreferrer">source</a>;

export default function LeadDetail() {
  const { id } = useParams();
  const [l, setL] = useState(null);
  const [tab, setTab] = useState("Overview");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [channel, setChannel] = useState("email");
  const [form, setForm] = useState({ status: "", notes: "", next_followup: "" });
  const load = useCallback(() => api(`/leads/${id}`).then((d) => { setL(d); setForm({ status: d.status, notes: d.notes || "", next_followup: d.next_followup?.slice(0, 10) || "" }); }).catch((x) => setErr(x.message)), [id]);
  useEffect(() => { load(); }, [load]);

  const act = (name, path, body) => async () => {
    setBusy(name); setErr("");
    try { await api(`/leads/${id}/${path}`, { method: "POST", body }); await load(); } catch (x) { setErr(x.message); }
    setBusy("");
  };
  const save = async () => {
    setErr("");
    try {
      await api(`/leads/${id}`, { method: "PATCH", body: { status: form.status, notes: form.notes, next_followup: form.next_followup ? new Date(form.next_followup).toISOString() : null } });
      await load();
    } catch (x) { setErr(x.message); }
  };
  if (!l) return err ? <div className="err">{err}</div> : <p className="muted">Loading…</p>;
  const c = l.company;
  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><h1>{c.name}</h1><p className="sub" style={{ marginBottom: 0 }}>{c.industry} · {c.country} · {c.website && <a href={c.website} target="_blank" rel="noopener noreferrer">{c.website}</a>}</p></div>
        <span className={`badge b-${l.status}`}>{label(l.status)}</span>
      </div>
      <div className="row" style={{ margin: "16px 0" }}>
        <button className="btn" disabled={!!busy} onClick={act("r", "research")}>{busy === "r" ? "Researching…" : l.research ? "Re-use research" : "Research Company"}</button>
        {l.research && <button className="btn ghost" disabled={!!busy} onClick={act("r2", "research", { force: true })}>Refresh research</button>}
        <button className="btn" disabled={!!busy} onClick={act("a", "audit")}>{busy === "a" ? "Auditing…" : "Audit Website"}</button>
        <button className="btn ghost" disabled={!!busy} onClick={act("o", "opportunities")}>{busy === "o" ? "Analyzing…" : "Find opportunities"}</button>
        <select aria-label="Channel" value={channel} onChange={(e) => setChannel(e.target.value)} style={{ width: 130 }}>
          {["email", "linkedin", "whatsapp", "followup", "proposal"].map((x) => <option key={x}>{x}</option>)}</select>
        <button className="btn" disabled={!!busy} onClick={act("g", "outreach", { channel })}>{busy === "g" ? "Drafting…" : "Generate Outreach"}</button>
      </div>
      {err && <div className="err" role="alert">{err}</div>}
      <div className="tabs" role="tablist">{TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}</div>

      {tab === "Overview" && (
        <div className="grid g2">
          <div className="card">
            <h2>Company</h2><p>{c.description || <span className="muted">No description.</span>}</p>
            {l.match_reason && <p><span className="badge b-infer">AI inference</span> {l.match_reason}</p>}
            {l.source && <p className="muted">Found via <Src url={l.source} /></p>}
          </div>
          <div className="card">
            <h2>Save lead</h2>
            <div className="field"><label htmlFor="st">Status</label><select id="st" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select></div>
            <div className="field"><label htmlFor="fu">Next follow-up</label><input id="fu" type="date" value={form.next_followup} onChange={(e) => setForm({ ...form, next_followup: e.target.value })} /></div>
            <div className="field"><label htmlFor="nt">Notes</label><textarea id="nt" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
            <button className="btn" onClick={save}>Save Lead</button>
          </div>
        </div>
      )}

      {tab === "Research" && (l.research ? (
        <div className="grid g2">
          <div className="card"><h2><span className="badge b-fact">Sourced facts</span></h2>
            <ul className="list">{l.research.facts.map((f, i) => <li key={i}>{f.claim} <Src url={f.source_url} /></li>)}{!l.research.facts.length && <li className="muted">No claims could be tied to a source.</li>}</ul></div>
          <div className="card"><h2><span className="badge b-infer">AI inference — not verified</span></h2>
            <ul className="list">{l.research.inferences.map((f, i) => <li key={i}>{f.statement}<div className="muted">{f.basis}</div></li>)}{!l.research.inferences.length && <li className="muted">None.</li>}</ul></div>
          <div className="card" style={{ gridColumn: "1/-1" }}><h2>Sources</h2><ul className="list">{l.research.sources.map((s) => <li key={s}><a href={s} target="_blank" rel="noopener noreferrer">{s}</a></li>)}</ul>
            <p className="muted">Researched {date(l.research.created_at)} · cached, so it won’t be re-run unless you refresh.</p></div>
        </div>
      ) : <p className="muted">No research yet. Use “Research Company” above.</p>)}

      {tab === "Website Audit" && (l.audit ? (
        <>
          <div className="card row" style={{ gap: 24 }}><div><div className="score">{l.audit.score ?? "—"}<small className="muted">/100</small></div><span className="muted">Weighted share of passed checks that were measured</span></div>
            <div className="muted">Audited {date(l.audit.created_at)} · {l.audit.url}</div></div>
          <div className="grid g2" style={{ marginTop: 12 }}>
            <div className="card"><h2>Strengths</h2><ul className="list">{l.audit.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
            <div className="card"><h2>Problems found</h2><ul className="list">{l.audit.problems.map((s, i) => <li key={i}>{s}</li>)}{!l.audit.problems.length && <li className="muted">None among measured checks.</li>}</ul></div>
            <div className="card"><h2>Recommended improvements</h2><ul className="list">{l.audit.recommendations.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
            <div className="card"><h2>Not assessed automatically</h2><ul className="list">{l.audit.not_assessed.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
          </div>
          <details className="card" style={{ marginTop: 12 }}><summary>All checks and evidence</summary>
            <div className="wrap"><table><thead><tr><th>Check</th><th>Result</th><th>Weight</th><th>Evidence</th></tr></thead><tbody>
              {l.audit.checks.map((k) => <tr key={k.key}><td>{k.label}</td><td>{k.passed === null ? "Not measured" : k.passed ? "Pass" : "Fail"}</td><td>{k.weight}</td><td className="muted">{k.evidence}</td></tr>)}</tbody></table></div></details>
        </>
      ) : <p className="muted">No audit yet. Use “Audit Website” above.</p>)}

      {tab === "Opportunities" && (l.opportunities.length ? l.opportunities.map((o) => (
        <div className="card" key={o.id} style={{ marginBottom: 10 }}>
          <div className="row"><span className="badge b-infer">AI-identified opportunity</span><b>{o.service}</b></div>
          <p><b>Problem:</b> {o.problem}</p>
          <b>Evidence</b><ul className="list">{o.evidence.map((e) => <li key={e.ref}>{e.text} {e.source_url && <Src url={e.source_url} />}</li>)}</ul>
          <p className="muted">{o.rationale}</p>
        </div>
      )) : <p className="muted">None yet. Run research and/or an audit, then “Find opportunities”.</p>)}

      {tab === "Contacts" && (
        <div className="wrap"><table><thead><tr><th>Name</th><th>Title</th><th>Email</th><th>Phone</th><th>LinkedIn</th><th>Provenance</th></tr></thead><tbody>
          {l.contacts.map((k) => <tr key={k.id}><td>{k.name || "—"}</td><td>{k.title || "—"}</td><td>{k.email || "—"}</td><td>{k.phone || "—"}</td>
            <td>{k.linkedin ? <a href={k.linkedin} target="_blank" rel="noopener noreferrer">profile</a> : "—"}</td>
            <td>{k.verified ? <span className="badge b-fact">seen on page</span> : <span className="badge b-infer">cited, not verified</span>} {k.source_url && <Src url={k.source_url} />}</td></tr>)}
          {!l.contacts.length && <tr><td colSpan={6} className="muted">No public contacts found. Nothing is guessed.</td></tr>}</tbody></table></div>
      )}

      {tab === "Outreach" && <Messages l={l} reload={load} setErr={setErr} />}
      {tab === "Activity" && <ul className="list">{l.activities.map((a, i) => <li key={i}>{new Date(a.created_at).toLocaleString()} — <b>{label(a.type)}</b> {a.detail}</li>)}</ul>}
    </>
  );
}

function Messages({ l, reload, setErr }) {
  const [edit, setEdit] = useState({});
  const emails = l.contacts.map((k) => k.email).filter(Boolean);
  const [to, setTo] = useState(emails[0] || "");
  const call = async (fn) => { setErr(""); try { await fn(); await reload(); } catch (x) { setErr(x.message); } };
  if (!l.messages.length) return <p className="muted">No drafts yet. Pick a channel and use “Generate Outreach”.</p>;
  return l.messages.map((m) => {
    const e = edit[m.id];
    return (
      <div className="msg" key={m.id}>
        <div className="row"><b>{m.channel}</b><span className={`badge b-${m.status}`}>{label(m.status)}</span></div>
        {e ? <>
          {m.channel === "email" && <input aria-label="Subject" value={e.subject} onChange={(ev) => setEdit({ ...edit, [m.id]: { ...e, subject: ev.target.value } })} />}
          <textarea aria-label="Body" style={{ minHeight: 160, marginTop: 8 }} value={e.body} onChange={(ev) => setEdit({ ...edit, [m.id]: { ...e, body: ev.target.value } })} />
          <button className="btn" onClick={() => call(async () => { await api(`/outreach/${m.id}`, { method: "PATCH", body: e }); setEdit({ ...edit, [m.id]: null }); })}>Save edits</button>
        </> : <>{m.subject && <div><b>Subject:</b> {m.subject}</div>}<pre>{m.body}</pre></>}
        {m.status !== "SENT" && <div className="row">
          {!e && <button className="btn ghost" onClick={() => setEdit({ ...edit, [m.id]: { subject: m.subject, body: m.body } })}>Edit</button>}
          {m.status === "DRAFT" && <button className="btn" onClick={() => call(() => api(`/outreach/${m.id}/approve`, { method: "POST" }))}>Approve</button>}
          {m.status === "APPROVED" && <>
            {m.channel === "email" && <input aria-label="Recipient" style={{ width: 240 }} placeholder="Recipient email" value={to} onChange={(ev) => setTo(ev.target.value)} list="rc" />}
            <datalist id="rc">{emails.map((x) => <option key={x} value={x} />)}</datalist>
            <button className="btn warn" onClick={() => { if (window.confirm(m.channel === "email" ? `Send this email to ${to}?` : "Mark as sent? (You send LinkedIn/WhatsApp messages yourself.)")) call(() => api(`/outreach/${m.id}/send`, { method: "POST", body: { to: m.channel === "email" ? to : null } })); }}>
              {m.channel === "email" ? "Send email" : "Mark as sent"}</button></>}
        </div>}
      </div>
    );
  });
}
