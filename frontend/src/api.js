// All calls go to our own backend. Secrets (OpenAI, SMTP) never reach the browser.
const KEY = "xylon_token";
export const token = { get: () => localStorage.getItem(KEY), set: (t) => localStorage.setItem(KEY, t), clear: () => localStorage.removeItem(KEY) };

export async function api(path, { method = "GET", body } = {}) {
  const res = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", ...(token.get() ? { Authorization: `Bearer ${token.get()}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && !path.startsWith("/auth/")) { token.clear(); window.location.assign("/login"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data;
}

export const STATUSES = ["NEW","RESEARCHED","QUALIFIED","MESSAGE_DRAFTED","CONTACTED","REPLIED","MEETING","PROPOSAL","WON","LOST","NOT_INTERESTED"];
export const SERVICES = ["Website Development","Website Redesign","E-commerce Development","Shopify Development","React Development","Custom Web Applications","AI Integration","AI Automation","CRM Automation","Lead Generation","Digital Marketing","SEO","Social Media Marketing","Business Automation","Maintenance & Support"];
export const label = (s) => (s || "").replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());
export const date = (d) => (d ? new Date(d).toLocaleDateString() : "—");
