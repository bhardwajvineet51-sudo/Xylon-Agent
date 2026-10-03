import { useEffect, useState } from "react";
import { api, label } from "../api";

const CARDS = [["total", "Total leads"], ["new", "New leads"], ["qualified", "Qualified leads"], ["messages_drafted", "Messages drafted"],
  ["contacted", "Contacted"], ["replies", "Replies"], ["meetings", "Meetings"], ["won", "Won"]];

export default function Dashboard() {
  const [d, setD] = useState(null);
  useEffect(() => { api("/dashboard").then(setD).catch(() => {}); }, []);
  if (!d) return <p className="muted">Loading…</p>;
  return (
    <>
      <h1>Dashboard</h1><p className="sub">Where your pipeline stands today.</p>
      {d.cards.total === 0 && <div className="note" style={{ marginBottom: 16 }}>No leads yet. Open <a href="/find">Find Leads</a> to run your first search.</div>}
      <div className="grid g4">{CARDS.map(([k, n]) => <div key={k} className="card stat"><b>{d.cards[k]}</b><span>{n}</span></div>)}</div>
      <h2 style={{ marginTop: 24 }}>Pipeline</h2>
      <div className="pipe">{d.pipeline.map((p) => <div key={p.status}><b>{p.count}</b><span>{label(p.status)}</span></div>)}</div>
    </>
  );
}
