import { useRef, useState, useEffect } from "react";
import { api, SERVICES } from "../api";
import { LeadTable } from "./Leads.jsx";

const blank = { industry: "", country: "", region: "", count: 10, company_size: "", keywords: "", service: "", require_website: true, recent_activity: false };

export default function FindLeads() {
  const [f, setF] = useState(blank);
  const [job, setJob] = useState(null);
  const [err, setErr] = useState("");
  const timer = useRef();
  useEffect(() => () => clearInterval(timer.current), []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const run = async (e) => {
    e.preventDefault(); setErr(""); setJob({ state: "running", stage: 0, stages: ["Searching", "Verifying websites", "Extracting public contacts", "Saving results"] });
    try {
      const body = { ...f, count: Number(f.count) };
      for (const k of ["region", "company_size", "keywords", "service"]) if (!body[k]) body[k] = null;
      const { job_id } = await api("/leads/find", { method: "POST", body });
      timer.current = setInterval(async () => {
        try {
          const j = await api(`/jobs/${job_id}`); setJob(j);
          if (j.state !== "running") clearInterval(timer.current);
        } catch (x) { clearInterval(timer.current); setErr(x.message); setJob(null); }
      }, 1500);
    } catch (x) { setErr(x.message); setJob(null); }
  };
  const running = job?.state === "running";
  return (
    <>
      <h1>Find leads</h1><p className="sub">Describe the companies you want. Contact details are only kept when they appear on the company’s own site.</p>
      <form className="card" onSubmit={run}>
        <div className="grid g3">
          <div className="field"><label htmlFor="i">Industry</label><input id="i" required value={f.industry} onChange={set("industry")} placeholder="Healthcare clinics" /></div>
          <div className="field"><label htmlFor="c">Country</label><input id="c" required value={f.country} onChange={set("country")} placeholder="United States" /></div>
          <div className="field"><label htmlFor="r">Region / city (optional)</label><input id="r" value={f.region} onChange={set("region")} /></div>
          <div className="field"><label htmlFor="n">Number of companies (max 30)</label><input id="n" type="number" min="1" max="30" value={f.count} onChange={set("count")} /></div>
          <div className="field"><label htmlFor="s">Company size (optional)</label><input id="s" value={f.company_size} onChange={set("company_size")} placeholder="11-50 employees" /></div>
          <div className="field"><label htmlFor="sv">Required service</label>
            <select id="sv" value={f.service} onChange={set("service")}><option value="">Any relevant service</option>{SERVICES.map((s) => <option key={s}>{s}</option>)}</select></div>
        </div>
        <div className="field"><label htmlFor="k">Keywords</label><input id="k" value={f.keywords} onChange={set("keywords")} placeholder="appointment booking, multi-location" /></div>
        <div className="row" style={{ marginBottom: 12 }}>
          <label style={{ fontWeight: 400 }}><input type="checkbox" style={{ width: "auto" }} checked={f.require_website} onChange={set("require_website")} /> Must have a working website</label>
          <label style={{ fontWeight: 400 }}><input type="checkbox" style={{ width: "auto" }} checked={f.recent_activity} onChange={set("recent_activity")} /> Recent public activity</label>
        </div>
        <button className="btn" disabled={running}>{running ? "Searching…" : "Find Leads"}</button>
      </form>
      {err && <div className="err" role="alert" style={{ marginTop: 12 }}>{err}</div>}
      {job && (
        <>
          <div className="steps" aria-live="polite">
            {job.stages.map((s, i) => <span key={s} className={job.state === "done" || i < job.stage ? "done" : i === job.stage && running ? "now" : ""}>{s}</span>)}
          </div>
          {job.state === "error" && <div className="err" role="alert">{job.error}</div>}
          {job.state === "done" && <>
            <p className="muted">{job.info}. Reasons below are AI inferences from search, not verified facts.</p>
            <LeadTable leads={job.result} />
            {job.result.map((l) => l.match_reason && <p key={l.id} className="muted"><b>{l.company.name}:</b> <span className="badge b-infer">AI inference</span> {l.match_reason}</p>)}
          </>}
        </>
      )}
    </>
  );
}
