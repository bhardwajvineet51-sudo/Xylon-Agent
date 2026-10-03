import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, date, label } from "../api";
import { LeadTable } from "./Leads.jsx";

// Research / Website Audits: choose a lead, then run the action on its detail page (manual trigger = cost control).
export function LeadList({ kind }) {
  const [leads, setLeads] = useState([]);
  useEffect(() => { api("/leads").then(setLeads).catch(() => {}); }, []);
  const title = kind === "research" ? "Research" : "Website audits";
  return (
    <>
      <h1>{title}</h1>
      <p className="sub">{kind === "research" ? "Research runs only when you ask, and results are cached." : "Audits run only when you ask, and results are cached."} Open a lead to run it.</p>
      <LeadTable leads={leads} />
    </>
  );
}

export function Outreach() {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  useEffect(() => { api(`/outreach${status ? `?status=${status}` : ""}`).then(setRows).catch(() => {}); }, [status]);
  return (
    <>
      <h1>Outreach</h1><p className="sub">Nothing is sent until you approve it. Review and send from each lead.</p>
      <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 180, marginBottom: 12 }}>
        <option value="">All</option><option value="DRAFT">Draft</option><option value="APPROVED">Approved</option><option value="SENT">Sent</option></select>
      <div className="wrap"><table><thead><tr><th>Company</th><th>Channel</th><th>Status</th><th>Preview</th></tr></thead><tbody>
        {rows.map((m) => <tr key={m.id}><td><Link to={`/leads/${m.lead_id}`}>{m.company}</Link></td><td>{m.channel}</td>
          <td><span className={`badge b-${m.status}`}>{label(m.status)}</span></td><td className="muted">{m.body.slice(0, 110)}…</td></tr>)}
        {!rows.length && <tr><td colSpan={4} className="muted">No messages yet. Open a lead and choose Generate Outreach.</td></tr>}</tbody></table></div>
    </>
  );
}

export function FollowUps() {
  const [rows, setRows] = useState([]);
  const load = () => api("/followups").then(setRows).catch(() => {});
  useEffect(() => { load(); }, []);
  return (
    <>
      <h1>Follow-ups</h1><p className="sub">Set follow-up dates from a lead’s Save Lead panel.</p>
      <div className="wrap"><table><thead><tr><th>Company</th><th>Due</th><th>Note</th><th /></tr></thead><tbody>
        {rows.map((f) => <tr key={f.id}><td><Link to={`/leads/${f.lead_id}`}>{f.company}</Link></td><td>{date(f.due_date)}</td><td>{f.note}</td>
          <td>{f.done ? <span className="badge b-SENT">Done</span> : <button className="btn ghost" onClick={() => api(`/followups/${f.id}/done`, { method: "POST" }).then(load)}>Mark done</button>}</td></tr>)}
        {!rows.length && <tr><td colSpan={4} className="muted">No follow-ups scheduled.</td></tr>}</tbody></table></div>
    </>
  );
}

export function Settings({ user }) {
  return (
    <>
      <h1>Settings</h1><p className="sub">Account and integrations.</p>
      <div className="card"><p><b>Signed in as</b> {user.email}</p>
        <p className="muted">API keys, SMTP and sender name are configured on the server via environment variables (see backend/.env.example). They are never shown or stored in the browser.</p></div>
    </>
  );
}
