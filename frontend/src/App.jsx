import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, AlertTriangle, ArrowUpRight, Bot, Check, CheckCircle2, ChevronRight, CircleHelp, Clock3, FileText, Headphones, LayoutDashboard, LifeBuoy, MessageCircle, MessageSquareText, Plus, Radio, RefreshCw, Search, Send, ShieldCheck, Sparkles, Ticket, Trash2, Upload, Users, X, Zap } from "lucide-react";

const API = (import.meta.env.VITE_API_BASE || "http://localhost:8000").trim().replace(/\/+$/, "");
const WS = (import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/admin").trim().replace(/\/+$/, "");
const makeId = () => `web-${Math.random().toString(36).slice(2, 9)}`;
const starter = [
  {role:"assistant",content:"Hi, I’m Mitra. Tell me what happened, and we’ll figure out the next step together. Please don’t share passwords, verification codes, or payment details."}
];
const tone = (value) => value === "High" || value === "Frustrated" ? "red" : value === "Medium" || value === "Concerned" ? "amber" : value === "Positive" ? "green" : "blue";

export default function App(){
  const [view,setView]=useState("overview");
  const [chatInput,setChatInput]=useState("");
  const [messages,setMessages]=useState(starter);
  const [sessionId,setSessionId]=useState(makeId);
  const selectedSessionRef=useRef("");
  const [sessions,setSessions]=useState([]);
  const [selectedSession,setSelectedSession]=useState("");
  const [analytics,setAnalytics]=useState(null);
  const [knowledge,setKnowledge]=useState([]);
  const [tickets,setTickets]=useState([]);
  const [actions,setActions]=useState([]);
  const [loading,setLoading]=useState(false);
  const [connected,setConnected]=useState(false);
  const [engineLabel,setEngineLabel]=useState("LOCAL RULES");
  const [notice,setNotice]=useState("");
  const [query,setQuery]=useState("");
  const [activeTab,setActiveTab]=useState("chat");
  const [knowledgeQuery,setKnowledgeQuery]=useState("");
  const [uploading,setUploading]=useState(false);
  const [planning,setPlanning]=useState(false);

  function flash(text){setNotice(text);window.setTimeout(()=>setNotice(current=>current===text?"":current),3600)}
  useEffect(()=>{selectedSessionRef.current=selectedSession},[selectedSession]);
  async function refresh(){
    try{
      const [s,k,t,a,h]=await Promise.all([
        fetch(`${API}/api/sessions`),fetch(`${API}/api/knowledge`),fetch(`${API}/api/tickets`),fetch(`${API}/api/actions`),fetch(`${API}/api/health`)
      ]);
      if(s.ok)setSessions(await s.json()); if(k.ok)setKnowledge(await k.json()); if(t.ok)setTickets(await t.json()); if(a.ok)setActions(await a.json());
      if(h.ok){const health=await h.json();setEngineLabel(health.analysis_engine==="featherless"&&health.external_ai_last_error?"FEATHERLESS · FALLBACK":health.analysis_engine==="featherless"?"FEATHERLESS AI":health.configured_provider==="featherless"?"FEATHERLESS · KEY NEEDED":health.external_ai_configured?"AI-ASSISTED":"LOCAL RULES")}
    }catch(error){console.warn("Mitra could not refresh support data:",error)}
  }
  useEffect(()=>{
    refresh();
    let socket;
    let retryTimer;
    let stopped=false;
    const connect=()=>{
      if(stopped)return;
      socket=new WebSocket(WS);
      socket.onopen=()=>setConnected(true);
      socket.onclose=()=>{setConnected(false);if(!stopped)retryTimer=window.setTimeout(connect,2500)};
      socket.onerror=()=>socket.close();
      socket.onmessage=(event)=>{
        try{
          const data=JSON.parse(event.data);
          if(data.type==="conversation_updated"){
            setSessions(old=>[data.session,...old.filter(s=>s.session_id!==data.session.session_id)]);
            if(data.session.session_id===selectedSessionRef.current)setAnalytics(data.session);
          }
          refresh();
        }catch(error){console.error("Mitra received an invalid live update:",error)}
      };
    };
    connect();
    return()=>{stopped=true;window.clearTimeout(retryTimer);socket?.close()};
  },[]);
  const shownSessions=useMemo(()=>sessions.filter(s=>`${s.customer_name} ${s.session_id} ${s.category}`.toLowerCase().includes(query.toLowerCase())),[sessions]);
  const shownKnowledge=useMemo(()=>knowledge.filter(article=>`${article.title} ${article.content}`.toLowerCase().includes(knowledgeQuery.toLowerCase())),[knowledge,knowledgeQuery]);

  async function sendMessage(event){
    event?.preventDefault(); const text=chatInput.trim();if(!text||loading)return;
    setMessages(old=>[...old,{role:"user",content:text}]);setChatInput("");setLoading(true);
    try{
      const res=await fetch(`${API}/api/chat`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId,message:text})});
      const data=await res.json();if(!res.ok)throw new Error(data.detail||"The support service could not process this message.");
      setMessages(old=>[...old,{role:"assistant",content:data.reply,provider_notice:data.provider_notice,context_articles:data.context_articles}]);setAnalytics(data.analytics);setSelectedSession(sessionId);await refresh();
    }catch(error){
      const answer="I couldn’t reach the support service, so your message hasn’t been analyzed. Please try again once the service is available.";
      setMessages(old=>[...old,{role:"assistant",content:answer}]);flash(error.message||"Support service is unavailable.");
    }finally{setLoading(false)}
  }
  async function runAction(action){
    const sid=selectedSession||sessionId;
    if(!sessions.some(session=>session.session_id===sid)){
      flash("Start a conversation or select an existing case before running an action.");
      return;
    }
    try{
      const res=await fetch(`${API}/api/actions`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sid,action,details:{subject:"Escalated issue from Mitra"}})});
      const data=await res.json();if(!res.ok)throw new Error(data.detail||"Action failed");flash(data.message);await refresh();
    }catch(error){flash(error.message||"The action could not be completed.")}
  }
  async function chooseSession(session){
    setSessionId(session.session_id);setSelectedSession(session.session_id);setAnalytics(session);setActiveTab("transcript");
    setMessages(session.messages||[]);
  }
  function startNewConversation(){
    setSessionId(makeId());setSelectedSession("");setAnalytics(null);setMessages(starter);setChatInput("");
  }
  async function uploadKnowledge(event){
    const files=Array.from(event.target.files||[]);
    event.target.value="";
    if(!files.length)return;
    setUploading(true);
    try{
      const documents=await Promise.all(files.map(async file=>{
        if(!/\.(txt|md)$/i.test(file.name))throw new Error(`${file.name}: upload a .txt or .md file.`);
        if(file.size>20000)throw new Error(`${file.name}: documents must be 20 KB or smaller.`);
        const content=(await file.text()).trim();
        if(content.length<40)throw new Error(`${file.name}: add at least 40 characters of support guidance.`);
        return {title:file.name.replace(/\.(txt|md)$/i,""),content};
      }));
      for(const document of documents){
        const response=await fetch(`${API}/api/knowledge`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(document)});
        const data=await response.json();
        if(!response.ok)throw new Error(data.detail||`Could not add ${document.title}.`);
      }
      await refresh();flash(`${files.length} knowledge ${files.length===1?"article":"articles"} added and ready for retrieval.`);
    }catch(error){flash(error.message||"The document could not be added.");await refresh()}
    finally{setUploading(false)}
  }
  async function removeKnowledge(article){
    try{
      const response=await fetch(`${API}/api/knowledge/${encodeURIComponent(article.id)}`,{method:"DELETE"});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"Could not remove this article.");
      await refresh();flash(`Removed "${article.title}" from the knowledge base.`);
    }catch(error){flash(error.message||"Could not remove this article.")}
  }
  async function generatePlan(session){
    const sid=session?.session_id||selectedSession||sessionId;
    setPlanning(true);
    try{
      const response=await fetch(`${API}/api/sessions/${encodeURIComponent(sid)}/action-plan`,{method:"POST"});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"Could not generate the action plan.");
      setAnalytics(current=>current?.session_id===sid?{...current,...data}:data);
      setSessions(current=>current.map(item=>item.session_id===sid?{...item,...data}:item));
      flash(data.plan_provider==="featherless"?"Featherless action plan updated from the full conversation.":data.plan_provider!=="local-rules"?"AI action plan updated from the full conversation.":"Suggested plan refreshed from the full conversation.");
    }catch(error){flash(error.message||"Could not generate the action plan.")}
    finally{setPlanning(false)}
  }
  const metrics={
    active:sessions.filter(s=>s.urgency==="High"||s.urgency==="Medium").length,
    high:sessions.filter(s=>s.urgency==="High").length,
    frustrated:sessions.filter(s=>s.sentiment==="Frustrated").length,
    tickets:tickets.length
  };

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Sparkles size={21}/></div><div><b>Mitra<span>•</span></b><small>CUSTOMER CARE STUDIO</small></div></div>
      <div className="workspace"><div className="workspace-mark">M</div><div><b>Mitra workspace</b><small>Customer experience</small></div><span className={`live-dot ${connected?"on":""}`}/></div>
      <div className="nav-label">PLATFORM</div>
      {[["overview","Overview",LayoutDashboard],["chat","Support chat",MessageCircle],["monitor","Live monitor",Activity],["knowledge","Knowledge base",FileText]].map(([id,label,Icon])=><button key={id} className={`nav ${view===id?"selected":""}`} onClick={()=>setView(id)}><Icon size={17}/>{label}{id==="monitor"&&metrics.active>0&&<span className="nav-count">{metrics.active}</span>}</button>)}
      <div className="nav-label space-top">OPERATIONS</div>
      <button className={`nav ${view==="tickets"?"selected":""}`} onClick={()=>setView("tickets")}><Ticket size={17}/>Ticket queue{tickets.length>0&&<span className="nav-count">{tickets.length}</span>}</button>
      <button className="nav" onClick={()=>setView("actions")}><Zap size={17}/>Resolution actions</button>
      <div className="side-bottom"><div className="guard-card"><ShieldCheck size={18}/><b>Safety guardrails active</b><p>Knowledge-grounded guidance. Sensitive details are redacted before storage.</p></div><div className="profile"><div className="profile-avatar">JL</div><div><b>Jordan Lee</b><small>Support administrator</small></div><CircleHelp size={17}/></div></div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="crumb">Workspace <ChevronRight size={14}/><b>{({overview:"Overview",chat:"Support chat",monitor:"Live monitor",knowledge:"Knowledge base",actions:"Resolution actions",tickets:"Ticket queue"})[view]}</b></div><div className="top-actions">{view==="chat"&&<button className="outline" onClick={startNewConversation}><Plus size={14}/> New conversation</button>}<span className={`connection ${connected?"good":""}`}><i/>{connected?"Live sync connected":"Local demo mode"}</span><div className="profile-avatar small">JL</div></div></header>
      <div className="content scroll">
        {view==="overview"&&<>
          <div className="hero"><div><div className="eyebrow"><span/> CONTEXT-AWARE SUPPORT OPERATIONS</div><h1>Support, with <em>context.</em></h1><p>Turn complex conversations into clear next steps — for customers and the agents who help them.</p></div><button className="primary" onClick={()=>setView("chat")}><MessageCircle size={16}/> Open support chat</button></div>
          <div className="metrics">
            <Metric icon={MessageSquareText} label="Conversations" value={sessions.length} sub="Live sessions tracked" color="violet"/>
            <Metric icon={AlertTriangle} label="Needs attention" value={metrics.active} sub="Medium or high urgency" color="orange"/>
            <Metric icon={Activity} label="High severity" value={metrics.high} sub="Prioritize human review" color="red"/>
            <Metric icon={Ticket} label="Escalation tickets" value={metrics.tickets} sub="Created in this demo" color="green"/>
          </div>
          <div className="grid-main">
            <section className="panel"><div className="panel-head"><div><h2>Live conversation feed</h2><p>Context and risk signals update as customers chat.</p></div><button className="subtle" onClick={()=>setView("monitor")}>Open monitor <ArrowUpRight size={14}/></button></div>
              <div className="feed">
                {sessions.length===0?<Empty icon={Radio} title="Waiting for conversations" text="Send a message in Support Chat to populate live monitoring."/>:sessions.slice(0,5).map(s=><SessionRow key={s.session_id} session={s} onClick={()=>chooseSession(s)}/>)}
              </div>
            </section>
            <section className="panel overview-side"><div className="panel-head"><div><h2>Resolution workflow</h2><p>Built for layered support issues.</p></div><Sparkles size={18} className="muted-icon"/></div>
              <Workflow number="01" title="Understand context" text="Ask clarifying questions and retrieve approved help articles."/>
              <Workflow number="02" title="Detect risk" text="Classify sentiment, intent, entities, and urgency."/>
              <Workflow number="03" title="Prepare escalation" text="Summarize facts, missing details, and suggested next actions."/>
              <Workflow number="04" title="Take safe action" text="Simulate ticket, refund request, or discount offer with clear confirmation."/>
            </section>
          </div>
          <div className="bottom-grid"><section className="panel"><div className="panel-head"><div><h2>Customer signal snapshot</h2><p>Signals are calculated from conversation text.</p></div><Activity size={17} className="muted-icon"/></div><div className="signal-row"><Signal label="Frustrated" value={metrics.frustrated} color="red"/><Signal label="High urgency" value={metrics.high} color="orange"/><Signal label="Knowledge articles" value={knowledge.length} color="violet"/></div></section>
          <section className="panel privacy"><ShieldCheck size={20}/><div><b>Privacy by design</b><p>Common email addresses and long card-like number sequences are redacted in stored chat text. Demo actions do not move money or contact external systems.</p></div></section></div>
        </>}
        {view==="chat"&&<div className="chat-layout"><section className="panel chat-panel"><div className="chat-title"><div className="bot-icon"><Bot size={20}/></div><div><h2>Mitra Support Assistant</h2><p><span className="live-dot on"/> Empathetic · Context-aware · Safety-first</p></div><span className="powered">{engineLabel}</span></div><div className="chat-messages scroll">{messages.map((m,i)=><div key={i} className={`bubble-row ${m.role==="user"?"user-row":""}`}><div className={`bubble-avatar ${m.role==="user"?"user-avatar":""}`}>{m.role==="user"?"You":<Bot size={16}/>}</div><div className={`bubble ${m.role==="user"?"user-bubble":""}`}><div className="bubble-label">{m.role==="user"?"You":"Mitra assistant"}</div><p>{m.content}</p>{m.provider_notice&&<div className="source-list"><span>{m.provider_notice}</span></div>}{m.context_articles?.length>0&&<div className="source-list"><b><ShieldCheck size={13}/> Grounded in support guide</b>{m.context_articles.map(a=><span key={a.id}>{a.id} · {a.title}</span>)}</div>}</div></div>)}{loading&&<div className="typing"><span/><span/><span/> Mitra is reviewing context…</div>}</div><form className="composer" onSubmit={sendMessage}><textarea value={chatInput} onChange={e=>setChatInput(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}}} placeholder="Tell us what you need a hand with…" rows={2}/><div className="composer-foot"><span><ShieldCheck size={13}/> Don’t include passwords, OTPs or payment details</span><button className="primary" type="submit" disabled={loading||!chatInput.trim()}><Send size={15}/> Send</button></div></form></section><aside className="panel chat-aside"><h3>Conversation context</h3><p className="aside-copy">Your conversation is analyzed for safe, relevant next steps.</p>{analytics?<><div className="context-score"><span>Severity score</span><b>{analytics.severity_score}<small>/100</small></b><div className="score-track"><span style={{width:`${analytics.severity_score}%`}}/></div></div><LabelValue label="Category" value={analytics.category}/><LabelValue label="Sentiment" value={analytics.sentiment} pill/><LabelValue label="Urgency" value={analytics.urgency} pill/><LabelValue label="Intent" value={analytics.intent}/><div className="entity-box"><b>Key entities</b><div>{(analytics.entities||[]).map(x=><span key={x}>{x}</span>)}</div></div><button className="outline full" onClick={()=>{setSelectedSession(sessionId);setView("monitor")}}>View agent analysis <ChevronRight size={15}/></button></>:<div className="aside-empty"><Sparkles size={22}/><b>Insights appear here</b><span>Send a message to classify intent, sentiment, urgency and relevant help articles.</span></div>}<div className="mini-guard"><ShieldCheck size={15}/><span>Guidance is based on demo support docs. Account-specific facts need human verification.</span></div></aside></div>}
        {view==="monitor"&&<>
          <div className="section-heading"><div><div className="eyebrow"><span/> LIVE OPERATIONS</div><h1>Conversation monitor</h1><p>Review the full context, risk signals, and suggested next actions.</p></div><span className={`connection ${connected?"good":""}`}><i/>{connected?"Live WebSocket":"Reconnecting"}</span></div>
          <div className="monitor-layout">
            <section className="panel"><div className="panel-head"><div><h2>Conversations</h2><p>{sessions.length} tracked sessions</p></div></div><div className="search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search by category or session"/></div><div className="feed">{shownSessions.length?shownSessions.map(s=><SessionRow key={s.session_id} session={s} onClick={()=>chooseSession(s)}/>):<Empty icon={Users} title="No sessions yet" text="Start a conversation in Support Chat."/ >}</div></section>
            <section className="panel analysis-panel"><div className="panel-head"><div><h2>Agent intelligence</h2><p>Structured summary and recommended plan</p></div><Sparkles size={18} className="muted-icon"/></div>{analytics||sessions.find(s=>s.session_id===selectedSession)?<Analysis session={analytics||sessions.find(s=>s.session_id===selectedSession)} onAction={runAction} onGeneratePlan={generatePlan} planning={planning}/>:<Empty icon={Activity} title="Select a conversation" text="Choose a live session to inspect its summary and action plan."/ >}</section>
          </div>
        </>}
        {view==="knowledge"&&<>
          <div className="section-heading">
            <div><div className="eyebrow"><span/> CONTEXT GROUNDING</div><h1>Knowledge base</h1><p>Upload approved support guides to ground Mitra’s troubleshooting replies.</p></div>
            <label className="primary upload-button"><Upload size={15}/>{uploading?"Adding documents…":"Upload .txt / .md"}<input type="file" accept=".txt,.md,text/plain,text/markdown" multiple disabled={uploading} onChange={uploadKnowledge}/></label>
          </div>
          <div className="kb-toolbar"><div className="search"><Search size={15}/><input value={knowledgeQuery} onChange={event=>setKnowledgeQuery(event.target.value)} placeholder="Search articles"/></div><span className="count-chip">{knowledge.length} articles · uploads are session-only</span></div>
          {shownKnowledge.length?<div className="knowledge-grid">{shownKnowledge.map(k=><article className="panel knowledge-card" key={k.id}><div className="kb-top"><span className="kb-id">{k.id}</span><div className="kb-actions"><span className={`source-badge ${k.custom?"custom":"built-in"}`}>{k.custom?"Uploaded":"Built-in"}</span><FileText size={18}/>{k.custom&&<button className="icon-button" aria-label={`Remove ${k.title}`} title="Remove uploaded article" onClick={()=>removeKnowledge(k)}><Trash2 size={15}/></button>}</div></div><h3>{k.title}</h3><p>{k.content}</p><span className="grounded"><ShieldCheck size={13}/> Used for context retrieval</span></article>)}</div>:<Empty icon={FileText} title="No matching articles" text="Try another search, or upload a .txt or .md support guide."/>}
          <div className="note"><AlertTriangle size={16}/><span>Only upload approved, non-sensitive support guidance. TXT and Markdown files up to 20 KB are supported. Documents and conversations are held in memory and reset when the backend restarts.</span></div>
        </>}
        {view==="actions"&&<><div className="section-heading"><div><div className="eyebrow"><span/> HUMAN-IN-THE-LOOP OPERATIONS</div><h1>Resolution actions</h1><p>Run safe demo actions for an active conversation. All actions are clearly simulated.</p></div></div><div className="action-grid"><ActionCard icon={Ticket} title="Create escalation ticket" text="Package the conversation summary for human support review." button="Create demo ticket" onClick={()=>runAction("create_ticket")}/><ActionCard icon={CheckCircle2} title="Simulate refund request" text="Record a refund request simulation; no money is moved." button="Simulate refund" onClick={()=>runAction("simulate_refund")}/><ActionCard icon={Zap} title="Generate discount code" text="Create an illustrative code that is not applied to any account." button="Generate code" onClick={()=>runAction("offer_discount")}/></div><section className="panel actions-log"><div className="panel-head"><div><h2>Action history</h2><p>Recent simulated operations</p></div></div>{actions.length?actions.map(a=><div className="log-row" key={a.id}><span className="log-icon"><Check size={15}/></span><div><b>{a.action.replaceAll("_"," ")}</b><p>{a.result}</p></div><time>{new Date(a.created_at).toLocaleTimeString()}</time></div>):<Empty icon={Zap} title="No actions yet" text="Run an action after starting a support conversation."/ >}</section></>}
        {view==="tickets"&&<><div className="section-heading"><div><div className="eyebrow"><span/> HUMAN-IN-THE-LOOP</div><h1>Ticket queue</h1><p>Escalations created from customer conversations, ready for agent review.</p></div><span className="count-chip">{tickets.length} open tickets</span></div><section className="panel actions-log"><div className="panel-head"><div><h2>Escalations</h2><p>Demo tickets include the conversation summary and creation time.</p></div><Ticket size={18} className="muted-icon"/></div>{tickets.length?tickets.map(ticket=><div className="log-row ticket-row" key={ticket.id}><span className="log-icon"><Ticket size={15}/></span><div><b>{ticket.id} · {ticket.subject}</b><p>{ticket.summary}</p><small>{ticket.session_id} · {new Date(ticket.created_at).toLocaleString()}</small></div><button className="outline" onClick={()=>{const session=sessions.find(item=>item.session_id===ticket.session_id);if(session){chooseSession(session);setView("monitor")}else flash("The conversation is no longer available.")}}>Review case <ChevronRight size={14}/></button></div>):<Empty icon={Ticket} title="No escalations yet" text="Create a ticket from the live monitor or resolution actions."/ >}</section></>}
        <footer className="footer"><span>© 2026 Mitra · Customer Care Studio</span><span><span className={`live-dot ${connected?"on":""}`}/>{connected?"Live updates active":"Backend connection required for live updates"}</span><span>Built around people, not tickets</span></footer>
      </div>
    </main>
    {notice&&<div className="toast"><CheckCircle2 size={17}/>{notice}<button onClick={()=>setNotice("")}><X size={14}/></button></div>}
  </div>
}

function Metric({icon:Icon,label,value,sub,color}){return <div className="metric"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${color}`}><Icon size={17}/></span></div><b>{value}</b><small>{sub}</small><div className={`metric-line ${color}`}/></div>}
function SessionRow({session:s,onClick}){return <button className="session-row" onClick={onClick}><div className="session-avatar"><MessageCircle size={17}/></div><div className="session-info"><b>{s.category||"Support conversation"}</b><span>{s.summary||s.session_id}</span><small>{s.session_id} · {s.messages?.length||0} messages</small></div><div className="session-signals"><span className={`pill ${tone(s.urgency)}`}>{s.urgency||"Low"}</span><span className={`pill ${tone(s.sentiment)}`}>{s.sentiment||"Neutral"}</span><ChevronRight size={15}/></div></button>}
function Workflow({number,title,text}){return <div className="workflow"><span>{number}</span><div><b>{title}</b><p>{text}</p></div></div>}
function Signal({label,value,color}){return <div className="signal"><span className={`signal-dot ${color}`}/><div><b>{value}</b><small>{label}</small></div></div>}
function Empty({icon:Icon,title,text}){return <div className="empty"><span><Icon size={20}/></span><b>{title}</b><p>{text}</p></div>}
function LabelValue({label,value,pill}){return <div className="label-value"><span>{label}</span>{pill?<span className={`pill ${tone(value)}`}>{value}</span>:<b>{value||"—"}</b>}</div>}
function Analysis({session:s,onAction,onGeneratePlan,planning}){return <div className="analysis-content"><div className="severity"><div><span>Severity score</span><b>{s.severity_score}<small>/100</small></b></div><div className="severity-bar"><span style={{width:`${s.severity_score}%`}}/></div><span className={`pill ${tone(s.urgency)}`}>{s.urgency} urgency</span></div><div className="analysis-facts"><LabelValue label="Sentiment" value={s.sentiment} pill/><LabelValue label="Category" value={s.category}/><LabelValue label="Intent" value={s.intent}/><LabelValue label="Key entities" value={(s.entities||[]).join(", ")}/></div><div className="summary"><h3><Sparkles size={15}/> Conversation summary</h3><p>{s.summary}</p><small>Root-cause hypothesis: {s.root_cause_hypothesis}</small></div><div className="summary"><h3><CircleHelp size={15}/> Missing information</h3>{s.missing_information?.length?<ul>{s.missing_information.map(x=><li key={x}>{x}</li>)}</ul>:<p>No additional required fields detected by the demo classifier.</p>}</div><div className="summary"><h3><CheckCircle2 size={15}/> Suggested action plan</h3><p className="plan-source">{s.plan_provider==="featherless"?"Featherless AI · Full conversation":s.plan_provider!=="local-rules"?"AI-assisted · Full conversation":"Context-aware · Full conversation"}</p><ol>{(s.action_plan||[]).map((x,i)=><li key={i}>{x}</li>)}</ol><button className="outline full plan-generate" disabled={planning} onClick={()=>onGeneratePlan(s)}><RefreshCw size={14}/>{planning?"Generating plan…":"Generate suggested action plan"}</button></div><div className="agent-actions"><button className="primary full" onClick={()=>onAction("create_ticket")}><Ticket size={15}/> Create escalation ticket</button><button className="outline full" onClick={()=>onAction("simulate_refund")}>Simulate refund request</button><button className="outline full" onClick={()=>onAction("offer_discount")}>Generate illustrative discount</button></div></div>}
function ActionCard({icon:Icon,title,text,button,onClick}){return <div className="panel action-card"><span className="action-icon"><Icon size={20}/></span><h3>{title}</h3><p>{text}</p><button className="outline full" onClick={onClick}>{button}<ChevronRight size={15}/></button></div>}
