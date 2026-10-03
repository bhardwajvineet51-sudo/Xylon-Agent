import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, token } from "./api";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Leads from "./pages/Leads.jsx";
import FindLeads from "./pages/FindLeads.jsx";
import LeadDetail from "./pages/LeadDetail.jsx";
import { Outreach, FollowUps, LeadList, Settings } from "./pages/Lists.jsx";

const NAV = [["/", "Dashboard"], ["/leads", "Leads"], ["/find", "Find Leads"], ["/research", "Research"],
  ["/audits", "Website Audits"], ["/outreach", "Outreach"], ["/followups", "Follow-ups"], ["/settings", "Settings"]];

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const nav = useNavigate();
  useEffect(() => {
    if (!token.get()) return setReady(true);
    api("/auth/me").then(setUser).catch(() => token.clear()).finally(() => setReady(true));
  }, []);
  if (!ready) return null;
  if (!user) return (
    <Routes>
      <Route path="/login" element={<Login onAuth={(u) => { setUser(u); nav("/"); }} />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
  return (
    <div className="shell">
      <nav className="side" aria-label="Main">
        <div className="brand">Xylon Technology<small>Growth Agent</small></div>
        {NAV.map(([to, name]) => <NavLink key={to} to={to} end={to === "/"}>{name}</NavLink>)}
        <div className="grow" />
        <div className="muted" style={{ padding: "0 10px 8px", fontSize: 12 }}>{user.email}</div>
        <button className="btn ghost" onClick={() => { token.clear(); setUser(null); nav("/login"); }}>Sign out</button>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/leads/:id" element={<LeadDetail />} />
          <Route path="/find" element={<FindLeads />} />
          <Route path="/research" element={<LeadList kind="research" />} />
          <Route path="/audits" element={<LeadList kind="audit" />} />
          <Route path="/outreach" element={<Outreach />} />
          <Route path="/followups" element={<FollowUps />} />
          <Route path="/settings" element={<Settings user={user} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
