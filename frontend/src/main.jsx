import React, { useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, AlertTriangle, BarChart3, Bell, BookOpen, ChevronRight, CircleDot, Command, Database, FileCheck2, Gauge, Globe2, Menu, Network, Search, ShieldCheck, SlidersHorizontal, Sparkles, Target, Users, X } from 'lucide-react'
import { api } from './api'
import './styles.css'

const nav = [
  { id: 'briefing', label: 'Operational Briefing', icon: Gauge },
  { id: 'entities', label: 'Entity Dossier', icon: Target },
  { id: 'network', label: 'Network Explorer', icon: Network },
  { id: 'analytics', label: 'Syndicate Analytics', icon: BarChart3 },
  { id: 'audit', label: 'Chain of Custody', icon: FileCheck2 },
]

const influencers = [
  { name: 'Arjun Mehta', code: 'PER-00481', role: 'Network coordinator', score: 98, tone: 'critical', edges: 47 },
  { name: 'Vikram Solanki', code: 'PER-01922', role: 'Financial operator', score: 91, tone: 'high', edges: 32 },
  { name: 'Priya Nair', code: 'PER-00714', role: 'Logistics facilitator', score: 84, tone: 'high', edges: 26 },
  { name: 'Rohan Das', code: 'PER-02841', role: 'Known associate', score: 68, tone: 'watch', edges: 18 },
]

const alerts = [
  { time: '04:18:32', type: 'COMMUNICATION BURST', text: '12 contacts across 3 clusters', severity: 'critical' },
  { time: '03:52:10', type: 'STRUCTURING PATTERN', text: '₹4.8L split across 9 accounts', severity: 'high' },
  { time: '02:41:09', type: 'GEO-FENCE BREACH', text: 'Vehicle entered restricted zone', severity: 'watch' },
  { time: '01:16:44', type: 'NEW ASSOCIATION', text: 'Confidence 0.87 · source corroborated', severity: 'info' },
]

function App() {
  const [active, setActive] = useState('briefing')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [apiStatus, setApiStatus] = useState('LIVE')
  const [selected, setSelected] = useState(null)
  const [searchResults, setSearchResults] = useState([])

  const filtered = useMemo(() => influencers.filter((person) => `${person.name} ${person.code} ${person.role}`.toLowerCase().includes(query.toLowerCase())), [query])

  async function search() {
    if (!query.trim()) return
    try { setSearchResults(await api.searchEntities(query)) } catch { setSearchResults([]) }
  }

  const title = nav.find((item) => item.id === active)?.label || 'Operational Briefing'

  return <div className="app-shell">
    <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark"><ShieldCheck size={20} /></div><div><strong>SENTINEL</strong><span>NETWORK INTELLIGENCE</span></div><button className="close-nav" onClick={() => setSidebarOpen(false)}><X size={18} /></button></div>
      <div className="classification"><CircleDot size={10} /> SYSTEM CLASSIFICATION <b>SEV-2</b></div>
      <nav className="nav-list">{nav.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${active === id ? 'active' : ''}`} onClick={() => { setActive(id); setSidebarOpen(false) }}><Icon size={18} /><span>{label}</span>{active === id && <ChevronRight size={15} />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="operator"><div className="avatar">AN</div><div><strong>ANANYA RAO</strong><span>Senior Investigator</span></div><SlidersHorizontal size={16} /></div><div className="secure"><ShieldCheck size={15} /> SESSION ENCRYPTED</div></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="menu-button" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button><div className="crumb"><span>CASEWORK / 2024-CR-047</span><ChevronRight size={14} /><strong>{title}</strong></div><div className="top-actions"><div className="system-status"><span className="pulse" /> {apiStatus} <small>API</small></div><button className="icon-button"><Bell size={18} /><i>3</i></button><button className="icon-button"><Command size={18} /></button></div></header>
      <div className="content">
        <section className="page-intro"><div><div className="eyebrow"><Sparkles size={13} /> INTELLIGENCE OPERATIONS / LIVE FEED</div><h1>{title}</h1><p>Cross-source signals, graph structure, and behavioral anomalies in one operational view.</p></div><div className="date-chip"><span>LAST SYNCHRONIZED</span><strong>13 SEP 2026 <b>04:20:18 IST</b></strong></div></section>
        {active === 'briefing' && <Briefing filtered={filtered} selected={selected} setSelected={setSelected} />}
        {active === 'entities' && <Entities query={query} setQuery={setQuery} search={search} results={searchResults} filtered={filtered} setSelected={setSelected} />}
        {active === 'network' && <NetworkView />}
        {active === 'analytics' && <Analytics />}
        {active === 'audit' && <Audit />}
      </div>
    </main>
    {selected && <div className="drawer-backdrop" onClick={() => setSelected(null)}><aside className="dossier" onClick={(event) => event.stopPropagation()}><button className="drawer-close" onClick={() => setSelected(null)}><X size={18} /></button><div className="eyebrow">PERSON / DOSSIER</div><h2>{selected.name}</h2><p className="mono">{selected.code} · {selected.role}</p><div className={`risk-orb ${selected.tone}`}><strong>{selected.score}</strong><span>RISK SCORE</span></div><div className="dossier-grid"><div><span>BETWEENNESS</span><strong>0.842</strong></div><div><span>PAGE RANK</span><strong>0.718</strong></div><div><span>LINKED EDGES</span><strong>{selected.edges}</strong></div><div><span>COMMUNITY</span><strong>CL-07</strong></div></div><button className="primary-button" onClick={() => setActive('network')}>OPEN NETWORK GRAPH <ChevronRight size={15} /></button></aside></div>}
  </div>
}

function Briefing({ filtered, setSelected }) { return <><section className="metrics"><Metric label="ACTIVE TARGETS" value="128" delta="+12.4%" icon={Target} /><Metric label="ACTIVE ALERTS" value="09" delta="3 critical" icon={AlertTriangle} danger /><Metric label="NETWORK LINKS" value="2,847" delta="+184 today" icon={Network} /><Metric label="DATA SOURCES" value="06" delta="All healthy" icon={Database} /></section><section className="dashboard-grid"><div className="panel graph-panel"><PanelHeader title="LIVE NETWORK TOPOLOGY" meta="2,847 EDGES / 128 NODES" /><div className="graph-stage"><div className="grid-lines" /><div className="graph-ring ring-a" /><div className="graph-ring ring-b" /><svg className="graph-lines" viewBox="0 0 700 350"><path d="M110 210 L245 105 L390 172 L530 92 L612 231 L410 286 L245 105 L110 210 M245 105 L410 286 M390 172 L612 231" fill="none" stroke="rgba(67,213,197,.37)" strokeWidth="1" /><path d="M390 172 L530 92 M110 210 L410 286" fill="none" stroke="rgba(243,176,74,.5)" strokeDasharray="4 6" /></svg>{[['node-red',110,210,'98'],['node-cyan',245,105,'84'],['node-amber',390,172,'91'],['node-cyan',530,92,'68'],['node-muted',612,231,'44'],['node-amber',410,286,'72']].map(([cl,x,y,label]) => <button key={`${x}-${y}`} className={`graph-node ${cl}`} style={{ left: `${x / 7}%`, top: `${y / 3.5}%` }} onClick={() => setSelected(influencers.find((p) => p.score === Number(label)) || influencers[0])}><span>{label}</span></button>)}</div><div className="graph-legend"><span><i className="dot red" /> HIGH RISK</span><span><i className="dot cyan" /> PERSON</span><span><i className="dot amber" /> FINANCIAL</span><span><i className="dot gray" /> LOW SIGNAL</span></div></div><div className="panel risk-panel"><PanelHeader title="HIGH-RISK CORE" meta="RANKED BY CENTRALITY" /><div className="people-list">{filtered.map((person, index) => <button className="person-row" key={person.code} onClick={() => setSelected(person)}><span className="rank">0{index + 1}</span><div className="person-main"><strong>{person.name}</strong><small>{person.code} · {person.role}</small></div><div className="score"><b className={person.tone}>{person.score}</b><span>{person.edges} edges</span></div><ChevronRight size={15} /></button>)}</div><button className="text-button">VIEW FULL ENTITY INDEX <ChevronRight size={14} /></button></div></section><section className="bottom-grid"><div className="panel alert-panel"><PanelHeader title="BEHAVIORAL ALERT STREAM" meta="AUTO-REFRESH 30S" /><div className="alert-list">{alerts.map((alert) => <div className="alert-row" key={alert.time}><span className={`alert-mark ${alert.severity}`} /><div><small>{alert.time} · {alert.type}</small><strong>{alert.text}</strong></div><ChevronRight size={14} /></div>)}</div></div><div className="panel health-panel"><PanelHeader title="PIPELINE HEALTH" meta="6 / 6 ONLINE" /><div className="health-chart"><div className="bar b1" /><div className="bar b2" /><div className="bar b3" /><div className="bar b4" /><div className="bar b5" /><div className="bar b6" /><div className="bar b7" /><div className="bar b8" /><div className="bar b9" /><div className="bar b10" /></div><div className="health-items"><span><i className="dot green" /> POSTGRESQL <b>42ms</b></span><span><i className="dot green" /> NEO4J GRAPH <b>68ms</b></span><span><i className="dot green" /> MONGODB <b>51ms</b></span></div></div></section></> }

function Metric({ label, value, delta, icon: Icon, danger }) { return <div className="metric-card"><div className={`metric-icon ${danger ? 'danger' : ''}`}><Icon size={18} /></div><span>{label}</span><strong>{value}</strong><small className={danger ? 'danger-text' : ''}>{delta}</small></div> }
function PanelHeader({ title, meta }) { return <div className="panel-header"><div><h3>{title}</h3><span>{meta}</span></div><button><MoreDots /></button></div> }
function MoreDots() { return <span className="more-dots">•••</span> }
function Entities({ query, setQuery, search, results, filtered, setSelected }) { return <section className="single-view"><div className="search-hero"><div className="eyebrow"><Search size={13} /> CROSS-SOURCE ENTITY RESOLUTION</div><h2>Find a person, account, vehicle, or location.</h2><div className="search-box"><Search size={19} /><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && search()} placeholder="Search by name, identifier, phone number, or plate..." /><button onClick={search}>SEARCH <ChevronRight size={15} /></button></div></div><div className="panel"><PanelHeader title="ENTITY INDEX" meta={`${results.length || filtered.length} MATCHES`} />{(results.length ? results : filtered).map((person) => <button className="entity-card" key={person.code} onClick={() => setSelected(person)}><div className="avatar small">{person.name.split(' ').map((n) => n[0]).join('')}</div><div><strong>{person.name}</strong><span>{person.code} · {person.role}</span></div><b className={`badge ${person.tone}`}>{person.tone.toUpperCase()}</b><ChevronRight size={15} /></button>)}</div></section> }
function NetworkView() { return <section className="single-view"><div className="network-hero"><div className="eyebrow"><Globe2 size={13} /> NEO4J / GRAPH EXPLORER</div><h2>Trace the network. Find the connective tissue.</h2><p>Interactive graph canvas is ready for the Cytoscape renderer in <span className="mono">core_logic_backup/NetworkGraph.jsx</span>.</p><div className="large-graph"><div className="network-halo" /><div className="network-core">NEXUS<span>ACTIVE GRAPH</span></div>{Array.from({ length: 13 }).map((_, i) => <span className={`orbit-node n${i + 1}`} key={i}>{i % 3 === 0 ? 'P' : i % 3 === 1 ? 'A' : 'O'}</span>)}</div></div></section> }
function Analytics() { return <section className="single-view"><div className="analytics-head"><div><div className="eyebrow"><BarChart3 size={13} /> GRAPH ANALYTICS ENGINE</div><h2>Syndicate behavior signals.</h2></div><button className="primary-button">RERUN ANALYSIS <Activity size={15} /></button></div><div className="analytics-grid"><div className="panel chart-card"><PanelHeader title="RISK VELOCITY" meta="LAST 30 DAYS" /><div className="line-chart"><svg viewBox="0 0 700 220" preserveAspectRatio="none"><path d="M0 190 C70 180 80 140 150 155 S220 170 280 90 S350 140 410 80 S480 110 540 38 S630 70 700 12" fill="none" stroke="#49d5c2" strokeWidth="3" /><path d="M0 190 C70 180 80 140 150 155 S220 170 280 90 S350 140 410 80 S480 110 540 38 S630 70 700 12 V220 H0Z" fill="url(#fill)" opacity=".25" /><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#49d5c2" /><stop offset="1" stopColor="#49d5c2" stopOpacity="0" /></linearGradient></defs></svg></div></div><div className="panel chart-card"><PanelHeader title="SIGNAL COMPOSITION" meta="BY SOURCE" /><div className="donut"><div className="donut-hole"><strong>74%</strong><span>CONFIDENCE</span></div></div><div className="donut-legend"><span><i className="dot cyan" /> TELECOM <b>42%</b></span><span><i className="dot amber" /> FINANCIAL <b>28%</b></span><span><i className="dot red" /> FIELD INTEL <b>18%</b></span></div></div></div></section> }
function Audit() { return <section className="single-view"><div className="audit-banner"><div className="audit-icon"><BookOpen size={22} /></div><div><div className="eyebrow">CRYPTOGRAPHIC INTEGRITY LAYER</div><h2>Immutable Chain of Custody</h2><p>Every investigation action is hash-chained and independently verifiable.</p></div><div className="verified"><ShieldCheck size={17} /> VERIFIED</div></div><div className="panel"><PanelHeader title="RECENT LEDGER BLOCKS" meta="SHA-256 / APPEND ONLY" />{['4f6c...8a21','a91b...f03d','0e32...7cd4','d441...102b'].map((hash, i) => <div className="ledger-row" key={hash}><span className="block-num">#{1284 - i}</span><div><strong>{['Graph traversal queried','Dossier accessed','Alert acknowledged','Evidence export generated'][i]}</strong><small>ANANYA RAO · 13 SEP 2026 0{4 - i}:1{i}:22 IST</small></div><code>{hash}</code><ShieldCheck size={15} /></div>)}</div></section> }

createRoot(document.getElementById('root')).render(<App />)
