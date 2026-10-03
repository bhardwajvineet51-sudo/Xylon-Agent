import { useState } from "react";
import { api, token } from "../api";

export default function Login({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ email: "", password: "", full_name: "" });
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try {
      const r = await api(`/auth/${mode}`, { method: "POST", body: f });
      token.set(r.token); onAuth(r.user);
    } catch (x) { setErr(x.message); }
  };
  return (
    <div className="login">
      <h1>Xylon Growth Agent</h1>
      <p className="sub">Research, qualify and reach out to B2B leads.</p>
      <form className="card" onSubmit={submit}>
        {err && <div className="err" role="alert">{err}</div>}
        {mode === "register" && <div className="field"><label htmlFor="n">Full name</label><input id="n" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></div>}
        <div className="field"><label htmlFor="e">Email</label><input id="e" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
        <div className="field"><label htmlFor="p">Password</label><input id="p" type="password" required minLength={mode === "register" ? 10 : 1} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
          {mode === "register" && <small className="muted">At least 10 characters.</small>}</div>
        <button className="btn" style={{ width: "100%" }}>{mode === "login" ? "Sign in" : "Create account"}</button>
        <p style={{ textAlign: "center", marginBottom: 0 }}>
          <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "login" ? "register" : "login"); }}>
            {mode === "login" ? "Create an account" : "I already have an account"}</a></p>
      </form>
    </div>
  );
}
