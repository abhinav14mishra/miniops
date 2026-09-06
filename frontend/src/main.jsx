import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';

const api = async (path, opts={}) => {
  const token = localStorage.getItem('token');
  const headers = {'Content-Type':'application/json', ...(opts.headers||{})};
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(path, {...opts, headers});
  if (!r.ok) throw new Error((await r.json()).detail || 'Request failed');
  return r.json();
};

function Login({onLogin}) {
  const [email,setEmail]=useState('admin@miniops.example.com');
  const [password,setPassword]=useState('admin123');
  const [error,setError]=useState('');
  const submit=async e=>{e.preventDefault();setError('');try{const x=await api('/api/v1/auth/login',{method:'POST',body:JSON.stringify({email,password})});localStorage.setItem('token',x.access_token);onLogin(x.user)}catch(err){setError(err.message)}};
  return <div className="login"><div className="login-card">
    <div className="brand"><span className="logo">M</span><div><b>MiniOps</b><small>Incident Operations</small></div></div>
    <h1>Welcome back</h1><p className="muted">Sign in to your operations workspace.</p>
    <form onSubmit={submit}><label>Email<input value={email} onChange={e=>setEmail(e.target.value)}/></label>
    <label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
    {error&&<div className="error">{error}</div>}<button className="primary">Sign in</button></form>
    <div className="demo">Demo: admin@miniops.example.com / admin123</div>
  </div></div>
}

function App({user,onLogout}) {
  const [tab,setTab]=useState('Overview');
  const [incidents,setIncidents]=useState([]);
  const [services,setServices]=useState([]);
  const [teams,setTeams]=useState([]);
  const [selected,setSelected]=useState(null);
  const [refresh,setRefresh]=useState(0);

  useEffect(()=>{
    api('/api/v1/incidents').then(setIncidents).catch(()=>{});
    api('/api/v1/services').then(setServices).catch(()=>{});
    api('/api/v1/teams').then(setTeams).catch(()=>{});
  },[refresh]);

  const open=i=>api(`/api/v1/incidents/${i.id}`).then(setSelected);
  const act=(id,path)=>api(`/api/v1/incidents/${id}/${path}`,{method:'POST'})
    .then(()=>{setSelected(null);setRefresh(x=>x+1)});

  const counts={
    open:incidents.filter(x=>x.status!=='RESOLVED').length,
    p1:incidents.filter(x=>x.priority==='P1'&&x.status!=='RESOLVED').length,
    ack:incidents.filter(x=>x.status==='ACKNOWLEDGED').length,
    resolved:incidents.filter(x=>x.status==='RESOLVED').length
  };

  return (
    <div className="shell">
      <aside>
        <div className="brand side"><span className="logo">M</span><div><b>MiniOps</b><small>Operations</small></div></div>
        {['Overview','Incidents','Services','Teams','On-Call','Escalation','Users','Audit Log'].map(x=>
          <button className={tab===x?'nav active':'nav'} onClick={()=>setTab(x)} key={x}>{x}</button>
        )}
        <div className="side-bottom">
          <div className="userbox"><div className="avatar">{user.name[0]}</div><div><b>{user.name}</b><small>{user.role}</small></div></div>
          <button className="logout" onClick={onLogout}>Sign out</button>
        </div>
      </aside>

      <main>
        <header>
          <div><h2>{tab}</h2><p className="muted">{tab==='Overview'?'Real-time operational health at a glance.':'Manage your incident operations.'}</p></div>
          <div className="header-actions"><span className="status-dot">All systems</span><span className="avatar mini">{user.name[0]}</span></div>
        </header>

        {tab==='Overview' ? (
          <>
            <div className="cards">
              <Metric label="Open incidents" value={counts.open}/>
              <Metric label="P1 critical" value={counts.p1}/>
              <Metric label="Acknowledged" value={counts.ack}/>
              <Metric label="Resolved" value={counts.resolved}/>
            </div>
            <section className="panel">
              <div className="panel-head"><h3>Active incidents</h3><button className="ghost" onClick={()=>setTab('Incidents')}>View all</button></div>
              <IncidentTable data={incidents.filter(x=>x.status!=='RESOLVED').slice(0,8)} onOpen={open}/>
            </section>
            <div className="grid2">
              <section className="panel">
                <div className="panel-head"><h3>Services</h3></div>
                {services.length ? services.map(s=>
                  <div className="service" key={s.id}><span className="dot"></span><div><b>{s.name}</b><small>{s.description||'Operational service'}</small></div><span className="pill good">{s.status}</span></div>
                ) : <Empty text="No services yet"/>}
              </section>
              <section className="panel">
                <div className="panel-head"><h3>Teams</h3></div>
                {teams.length ? teams.map(t=>
                  <div className="service" key={t.id}><div className="team-icon">T</div><div><b>{t.name}</b><small>{t.description||'Response team'}</small></div></div>
                ) : <Empty text="No teams yet"/>}
              </section>
            </div>
          </>
        ) : tab==='Incidents' ? (
          <section className="panel"><IncidentTable data={incidents} onOpen={open}/></section>
        ) : tab==='Services' ? (
          <section className="panel"><List data={services} empty="No services configured."/></section>
        ) : tab==='Teams' ? (
          <section className="panel"><List data={teams} empty="No teams configured."/></section>
        ) : (
          <section className="panel"><Empty text={`${tab} management is available through the API in this local validation build; the UI modules are reserved for the next polish pass.`}/></section>
        )}
      </main>

      {selected && (
        <div className="drawer-bg" onClick={()=>setSelected(null)}>
          <div className="drawer" onClick={e=>e.stopPropagation()}>
            <button className="close" onClick={()=>setSelected(null)}>×</button>
            <span className={`priority ${selected.incident.priority}`}>{selected.incident.priority}</span>
            <h2>{selected.incident.title}</h2>
            <p className="muted">{selected.incident.incident_number} · {selected.incident.status}</p>
            <div className="actions">
              {selected.incident.status!=='ACKNOWLEDGED'&&selected.incident.status!=='RESOLVED'&&
                <button className="primary" onClick={()=>act(selected.incident.id,'acknowledge')}>Acknowledge</button>}
              {selected.incident.status!=='RESOLVED'&&
                <button className="danger" onClick={()=>act(selected.incident.id,'resolve')}>Resolve</button>}
            </div>
            <h3>Timeline</h3>
            {selected.events.map(e=>
              <div className="timeline" key={e.id}><span></span><div><b>{e.event_type.replaceAll('_',' ')}</b><small>{e.message}</small></div></div>
            )}
            <h3>Notes</h3>
            {selected.notes.length ? selected.notes.map(n=><div className="note" key={n.id}>{n.body}</div>) : <Empty text="No notes yet."/>}
          </div>
        </div>
      )}
    </div>
  );
}

const Metric=({label,value})=><div className="metric"><small>{label}</small><strong>{value}</strong><span>Current</span></div>;
const Empty=({text})=><div className="empty">{text}</div>;
function List({data,empty}){return data.length?data.map(x=><div className="list-row" key={x.id}><b>{x.name}</b><span>{x.description||''}</span></div>):<Empty text={empty}/>};
function IncidentTable({data,onOpen}){return data.length?<div className="table"><div className="tr th"><span>Incident</span><span>Priority</span><span>Status</span><span>Service</span></div>{data.map(i=><button className="tr" key={i.id} onClick={()=>onOpen(i)}><span><b>{i.incident_number}</b><small>{i.title}</small></span><span><em className={`priority ${i.priority}`}>{i.priority}</em></span><span><em className={`state ${i.status}`}>{i.status}</em></span><span>Service #{i.service_id}</span></button>)}</div>:<Empty text="No incidents. Your operations are clear."/>}

createRoot(document.getElementById('root')).render(<Root/>);
function Root(){const [user,setUser]=useState(null);useEffect(()=>{if(localStorage.getItem('token'))api('/api/v1/auth/me').then(setUser).catch(()=>localStorage.removeItem('token'))},[]);if(!user)return <Login onLogin={setUser}/>;return <App user={user} onLogout={()=>{localStorage.removeItem('token');setUser(null)}}/>}
