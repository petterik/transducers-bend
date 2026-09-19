// Isolated CPU experiment. Recognition and proof use typed terms only.
// No generated-C matching, source names, or fixed state/tag positions.
type GLSummary = {k:string; pc:GP; inputs:Set<number>; fast:(name:string)=>string};
type GLRecord = {key:string; k:string; refs:Set<string>};
type GLProbe = {
  candidate:GLSummary; chain:Set<string>; keys:Map<string,string>;
  width:number; sites:Set<HTerm>; edges:{pc:GP; xs:GX[]}[];
  calls:number; callPaths:GP[]; guard?:GP; proved:boolean; rejection?:string;
};
type GLContext = {id:string; keys:Set<string>; candidateKey:string; candidate:GLSummary};
type GLState = {
  summaries:Map<string,GLSummary>; records:Map<string,GLRecord>;
  context?:GLContext; attempts:number; clones:number; suppress:number;
  trivial:Map<string,{generic:string; doms:number[]}>;
};
const GL_ENABLE_LOOP = false;
const GL_STATES = new WeakMap<File,GLState>();
const GL_HOST = '#if !defined(__METAL_VERSION__) && !defined(__CUDACC__) && !defined(__CUDACC_RTC__)';
function gl_state(fl:File):GLState {
  let s=GL_STATES.get(fl);
  if (!s) GL_STATES.set(fl,s={summaries:new Map(),records:new Map(),attempts:0,clones:0,suppress:0,trivial:new Map()});
  return s;
}
function gl_key(fl:File,ck:Call,ers:HTerm[]):string {
  return [ck.k,...ers.map(e=>JSON.stringify(lay_of(fl.book,e)))].join('|');
}
function gl_vars(x:GX):number[] {
  return x.op === 'var' ? [x.id!] : x.a.flatMap(gl_vars);
}
function gl_sub(x:GX, values:GX[]):GX {
  if (x.op === 'var') return values[x.id!] ?? (()=>{throw new GReject('substitution scope')})();
  return {...x,a:x.a.map(a=>gl_sub(a,values))};
}
function gl_render(x:GX):string {
  if (x.op === 'var') return `r${x.id}`;
  if (x.op === 'lit') return `${x.n}ull`;
  if (x.op === 'eq') return `(${gl_render(x.a[0])} == ${gl_render(x.a[1])})`;
  throw new GReject('entry expression');
}
function gl_native_key(fl:File,ck:Call,ers:HTerm[]):string {
  const key=gl_key(fl,ck,ers), cx=gl_state(fl).context;
  return cx?.keys.has(key) ? `${key}|guarded-loop:${cx.id}` : key;
}
function gl_finish(fl:File,ck:Call,ers:HTerm[],name:string,emitted:[string,string,Set<string>]):void {
  const state=gl_state(fl), key=gl_key(fl,ck,ers), cx=state.context;
  const original=emitted[1];
  if (cx) {
    // Context is part of the native cache key; generic callers never reuse this.
    if (cx.keys.has(key)) {
      if (key === cx.candidateKey) emitted[1]=cx.candidate.fast(name);
      emitted[1]=[GL_HOST,emitted[1],'#endif'].join('\n');
    }
    return;
  }
  state.records.set(name,{key,k:ck.k,refs:emitted[2]});
  if (state.suppress) return;
  const scalar=guarded_scalar(fl,ck,ers,name,original);
  if (!GL_ENABLE_LOOP) {
    if (scalar !== null) emitted[1]=scalar;
    return;
  }
  // Only loops with bounded scalar signatures qualify. Unrelated helpers remain
  // byte-for-byte original in loop mode, including fallback-heavy direct calls.
  const sig=sig_def(fl,ck.k), width=sig.lays.flatMap(l=>l.ks).length;
  if (width>12 || sig.ret.ks.length>8 || [...sig.lays,sig.ret].some(l=>l.ks.includes('box')))
    return;
  const def=fl.book.tlds[ck.k] as Def;
  if (!term_any(fl,def.h!,t=>call_kind(fl,t)?.k===ck.k)) return;
  if (++state.attempts>64 || state.clones>=16) return;
  const descendants=new Map<string,GLRecord>();
  const collect=(n:string,depth=0):void=>{
    if (depth>8 || descendants.size>24) throw new GReject('call graph budget');
    const r=state.records.get(n);
    if (!r || descendants.has(n)) return;
    descendants.set(n,r);
    r.refs.forEach(n=>collect(n,depth+1));
  };
  try {
    collect(name);
    const candidates=[...descendants].filter(([,r])=>state.summaries.has(r.key));
    if(process.env.BEND_GUARDED_TRACE) console.error("loop candidates",ck.k,candidates.map(x=>x[1].k));
    if (candidates.length!==1) return;
    const [candidateName,record]=candidates[0], candidate=state.summaries.get(record.key)!;
    // Reverse reachability identifies exactly the native helper chain to clone.
    const chainNames=new Set([candidateName]);
    for(let i=0;i<9;i++) for(const [n,r] of descendants)
      if ([...r.refs].some(n=>chainNames.has(n))) chainNames.add(n);
    if (!chainNames.has(name) || chainNames.size>6) return;
    const keys=new Map<string,string>();
    for(const n of chainNames) {
      const r=descendants.get(n)!;
      if (keys.has(r.k) && keys.get(r.k)!==r.key) throw new GReject('polymorphic chain');
      keys.set(r.k,r.key);
    }
    const probe:GLProbe={candidate,chain:new Set(keys.keys()),keys,width,
      sites:new Set(),edges:[],calls:0,callPaths:[],proved:false};
    guarded_scalar(fl,ck,ers,name,original,probe);
    if (!probe.proved) {
      if (process.env.BEND_LOOP_REPORT) fs.appendFileSync(process.env.BEND_LOOP_REPORT,
        JSON.stringify({callee:ck.k,rejected:probe.rejection??'no proof'})+'\n');
      return;
    }
    const guard=probe.guard!.map(([x,y])=>`${y?'':'!'}${gl_render(x)}`).join(' && ');
    // Re-emit the typed loop and bounded direct chain. This preserves callback
    // order, original polling, failure paths, and all back-edge state updates.
    state.context={id:name,keys:new Set(keys.values()),candidateKey:record.key,candidate};
    state.clones++;
    let fast:string;
    try { fast=emit_native(fl,ck,ers); }
    finally { state.context=undefined; }
    const generic=name+'_loop_generic';
    const decl=sig.lays.flatMap(l=>l.ks).map((k,i)=>`, ${lay_c(k)} r${i}`).join('');
    const actual=Array.from({length:width},(_,i)=>`, r${i}`).join('');
    emitted[1]=[GL_HOST,
      `/* guarded_loop: typed entry guard; ${probe.edges.length} proven back-edge paths; ${chainNames.size} scoped helpers */`,
      original.replace(`${name}(`,`${generic}(`),
      `INLINE Term ${name}(Env e, THR Term* o${decl}) {`,
      `  if (${guard}) return ${fast}(e, o${actual});`,
      `  return ${generic}(e, o${actual});`,
      '}', `#define ${name}_loop_trivial ${generic}`, '#else',original,
      `#define ${name}_loop_trivial ${name}`, '#endif'].join('\n');
    let at=0;
    const trivial:number[]=[];
    sig.lays.forEach((l,i)=>{
      const slot=at; at+=l.ks.length;
      if (ty_adt(fl.book,sig.live[i][2])?.k === 'Nat' && l.ks.length===1
        && probe.edges.every(e=>{
          const x=e.xs[slot];
          return x.op==='offset' && x.a[0].op==='var' && x.a[0].id===slot && x.a[1].n===-1;
        })) trivial.push(i);
    });
    state.trivial.set(name,{generic:name+'_loop_trivial',doms:trivial});
    emitted[2].add(fast);
    // Native helpers are emitted in dependency order, with no forward prototypes.
    fl.spins.splice(fl.spins.indexOf(emitted),1);
    fl.spins.push(emitted);
    if (process.env.BEND_LOOP_REPORT) fs.appendFileSync(process.env.BEND_LOOP_REPORT,
      JSON.stringify({callee:ck.k,name,fast,guard:probe.guard,backEdges:probe.edges.length,
        chain:[...keys.keys()],width,trivialNatDomains:trivial})+'\n');
  } catch(e) {
    if (!(e instanceof GReject)) throw e;
    if(process.env.BEND_GUARDED_TRACE) console.error(`loop reject ${ck.k}: ${e.message}`);
  }
}

// This is a compile-time profitability choice only. Every generic path is valid;
// no runtime threshold branch is added. A literal zero/one countdown is cheap.
function gl_call_name(fl:File,name:string,ck:Call):string {
  const entry=gl_state(fl).trivial.get(name);
  if (!entry) return name;
  const small=(t:HTerm,depth=0):boolean=>{
    const x=Bend.term_strip(t);
    if (x.$!=='Ctr') return false;
    if (x.k==='Zero') return true;
    return depth===0 && x.k==='Succ' && x.x.length===1 && small(x.x[0],1);
  };
  if (!entry.doms.some(i=>small(ck.args[i]))) return name;
  if(process.env.BEND_LOOP_REPORT) fs.appendFileSync(process.env.BEND_LOOP_REPORT,
    JSON.stringify({callee:ck.k,trivialCaller:true})+'\n');
  return entry.generic;
}

// A context applies only while emitting its proven helper chain. An ordinary
// dependency emitted on demand must not inherit fast versions of shared callees.
function emit_native(fl:File,ck:Call,ers:HTerm[]):string {
  const state=gl_state(fl), cx=state.context;
  if (!cx || cx.keys.has(gl_key(fl,ck,ers))) return emit_native_core(fl,ck,ers);
  state.context=undefined;
  state.suppress++;
  try { return emit_native_core(fl,ck,ers); }
  finally { state.suppress--; state.context=cx; }
}
