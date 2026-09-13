# AI-Powered Criminal Network Analysis - v0 Frontend Architecture Plan

This document contains the exact architecture and prompting instructions to generate a world-class, hackathon-winning frontend using v0.dev. 

## Instructions for You
1. Go to [v0.dev](https://v0.dev).
2. **Upload** the files `client.js` and `NetworkGraph.jsx` (from your `core_logic_backup` folder) as attachments to your prompt. This gives v0 your actual backend connections and graph logic.
3. **Copy and paste** the "Master Prompt" below into the v0 chat to generate your initial application layout and dashboard.

---

## 🚀 The Master Prompt for v0

**Context:** 
You are an elite frontend architect and UI/UX designer. I am building an "AI-Powered Criminal Network Analysis System" for a major government hackathon (Smart India Hackathon). It is a highly advanced tool for law enforcement to track syndicates, view Neo4j network graphs, and analyze financial/communication anomalies.

**Design System Requirements:**
- **Aesthetic:** Create a high-end, cutting-edge intelligence dashboard (think Palantir Gotham, but modernized). It should look highly secure, cinematic, and incredibly polished. 
- **Theme:** I want a jaw-dropping UI. Choose a premium Dark Mode (deep navy/black with electric blue/neon accents) OR an ultra-clean glassmorphic Light Mode. 
- **Components:** Rely heavily on Shadcn UI and Tailwind CSS. Use sophisticated micro-interactions, blurred backdrops, and beautiful layout alignments.

**Core Technical Requirements:**
- I have attached two files: `client.js` (my backend API connector) and `NetworkGraph.jsx` (my Cytoscape graph renderer).
- When writing data fetching logic, **do not write dummy fetch calls**. Import and use the methods from my `client.js` (e.g., `api.getInfluencers()`, `api.getAlerts()`).
- Whenever a topology or network graph needs to be rendered, import and place my `<NetworkGraph />` component.

**Required Layout & Routing:**
Create a master layout with a collapsible sidebar navigation containing the following views:

1. **Dashboard (Operational Briefing):**
   - High-level KPI cards (Total active targets, active alerts, network links).
   - A sleek list/table of the "High-Risk Core" suspects.
   - A designated area rendering a preview of the `<NetworkGraph />`.
   - A real-time feed of behavioral alerts.

2. **Entity Search & Dossier:**
   - A powerful, globally accessible search bar utilizing `api.searchEntities()`.
   - A complex data-table showing search results with Shadcn Badges for risk levels (Critical, High, Low).

3. **Network Graph Explorer:**
   - A full-screen, highly immersive view rendering the `<NetworkGraph />` component.

4. **Syndicate Analytics:**
   - Utilize `recharts` to render beautiful area charts and radar charts for financial structuring and communication bursts.

5. **Chain of Custody Audit:**
   - An "Immutable Ledger" view (data table) showing cryptographic SHA-256 hashes of all system actions to prove to a jury that the AI evidence hasn't been tampered with.

**Your First Task:**
Please generate the complete `AppShell` (Sidebar + Top Navigation) and the `Dashboard` page. Focus heavily on making the UI look stunning, professional, and ready for a major hackathon presentation.
