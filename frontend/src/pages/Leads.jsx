import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, STATUSES, label, date } from "../api";

export function LeadTable({ leads, sort, onSort }) {
  const H = ({ k, children }) => <th className={k ? "s" : ""} onClick={() => k && onSort?.(k)}>{children}{sort?.key === k ? (sort.order === "asc" ? " ↑" : " ↓") : ""}</th>;
  return (
    <div className="wrap"><table>
      <thead><tr><H k="company">Company</H><H>Industry</H><H>Country</H><H>Contact</H><H k="status">Status</H><H>Outreach</H><H>Services</H><H k="next_followup">Next follow-up</H></tr></thead>
      <tbody>
        {leads.map((l) => (
          <tr key={l.id}>
            <td><Link to={`/leads/${l.id}`}><b>{l.company.name}</b></Link><div className="muted">{l.company.website?.replace(/^https?:\/\//, "")}</div></td>
            <td>{l.company.industry}</td><td>{l.company.country}</td>
            <td>{l.contact ? <>{l.contact.email || l.contact.phone || l.contact.name || "—"}{l.contact.verified && <div className="muted">found on site</div>}</> : <span className="muted">none found</span>}</td>
            <td><span className={`badge b-${l.status}`}>{label(l.status)}</span></td>
            <td><span className={`badge b-${l.outreach_status}`}>{label(l.outreach_status)}</span></td>
            <td>{l.recommended_services.join(", ") || <span className="muted">—</span>}</td>
            <td>{date(l.next_followup)}</td>
          </tr>
        ))}
        {!leads.length && <tr><td colSpan={8} className="muted">No leads match. Adjust the filters or find new leads.</td></tr>}
      </tbody>
    </table></div>
  );
}

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [q, setQ] = useState(""); const [status, setStatus] = useState("");
  const [sort, setSort] = useState({ key: "created_at", order: "desc" });
  useEffect(() => {
    const t = setTimeout(() => {
      const p = new URLSearchParams({ sort: sort.key, order: sort.order });
      if (q) p.set("q", q); if (status) p.set("status", status);
      api(`/leads?${p}`).then(setLeads).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q, status, sort]);
  return (
    <>
      <h1>Leads</h1><p className="sub">{leads.length} leads</p>
      <div className="row" style={{ marginBottom: 12 }}>
        <input style={{ width: 260 }} placeholder="Search company, industry or domain" aria-label="Search" value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
        </select>
      </div>
      <LeadTable leads={leads} sort={sort} onSort={(k) => setSort((s) => ({ key: k, order: s.key === k && s.order === "desc" ? "asc" : "desc" }))} />
    </>
  );
}
