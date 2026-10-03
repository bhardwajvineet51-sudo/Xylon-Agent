import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Dev proxy: the browser only talks to /api, so no API keys or backend URLs live in frontend code.
export default defineConfig({ plugins: [react()], server: { proxy: { "/api": "http://localhost:8000" } } });
