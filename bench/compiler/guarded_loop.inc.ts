// Isolated CPU experiment. Recognition and proof use typed terms only.
// No generated-C matching, source names, or fixed state/tag positions.
type GLSummary = {
  k:string; pc:GP; inputs:Set<number>; ret:Lay; outputs:GX[];
  fast:(name:string)=>string
};
type GLRecord = {key:string; k:string; refs:Set<string>};
type GLProbe = {
  candidate:GLSummary; chain:Set<string>; keys:Map<string,string>;
  width:number; sites:Set<HTerm>; edges:{pc:GP; xs:GX[]}[];
  calls:number; callPaths:GP[]; guard?:GP; proved:boolean; rejection?:string;
};
type GLTreeControl = {lay:Lay; left:number};
type GLContext = {
  id:string; keys:Set<string>; candidateKey:string; candidate:GLSummary;
  treeK?:string; control?:GLTreeControl
};
type GLState = {
  summaries:Map<string,GLSummary>; records:Map<string,GLRecord>;
  context?:GLContext; attempts:number; clones:number; suppress:number;
  trivial:Map<string,{generic:string; doms:number[]}>;
};
const GL_ENABLE_LOOP = false;
const GL_ENABLE_TREE = true;
const GL_SOURCE_GATE = false;
const GL_STATES = new WeakMap<object,GLState>();
const GL_HOST = '#if !defined(__METAL_VERSION__) && !defined(__CUDACC__) && !defined(__CUDACC_RTC__)';
function gl_state(fl:Carb):GLState {
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

// A structural tree driver has a boxed recursive source and two recursive
// calls, with one result fed into the other. It cannot use the tail-loop
// entry proof, but it can still reuse a proven scalar callback chain. This
// predicate deliberately knows nothing about adapter names or generated C.
function gl_tree_flat(fl:Carb,ck:Call):boolean {
  if (!GL_ENABLE_LOOP || !GL_ENABLE_TREE) return false;
  // Without a previously proved scalar callback there is no safe tree
  // specialization to request; leave the ordinary work-loop lowering alone.
  const gs=gl_state(fl);
  if (gs.summaries.size===0 || ![...gs.records.values()].some(r=>gs.summaries.has(r.key))) return false;
  const tld=fl.book.tlds[ck.k] as Def;
  if (!tld?.h) return false;
  const sig=sig_def(fl,ck.k);
  if (sig.lays.length===0 || sig.lays[0].ks.length!==1 || sig.lays[0].ks[0]!=='box') return false;
  if (sig.lays.flatMap(l=>l.ks).length>16 || sig.ret.ks.length>8) return false;
  let self=0, nonTail=0, bad=false;
  term_any(fl,tld.h,(t,tail)=>{
    const call=call_kind(fl,t);
    if (call?.k===ck.k) {
      self++;
      if (!tail) nonTail++;
      if (call.bang) bad=true;
    }
    if (call?.bang===true || (t.$==='Let' && t.k.length>=2)) bad=true;
    return false;
  });
  // The elaborated term visits each annotated recursive application twice;
  // this is the structural two-branch tree shape (four visits, two non-tail).
  return !bad && self===4 && nonTail===2;
}

// Re-emit a tree driver while the context maps its statically known callback
// chain to guarded scalar helpers. The tree source/control representation is
// unchanged; every callback helper retains its own generic fallback.
function gl_tree_finish(fl:File,ck:Call,ers:HTerm[],name:string,emitted:[string,string,Set<string>]):boolean {
  const state=gl_state(fl);
  if (state.suppress || !gl_tree_flat(fl,ck) || state.attempts++>64 || state.clones>=16) return false;
  const descendants=new Map<string,GLRecord>();
  const collect=(n:string,depth=0):void=>{
    if (depth>8 || descendants.size>24) throw new GReject('tree call graph budget');
    const r=state.records.get(n);
    if (!r || descendants.has(n)) return;
    descendants.set(n,r);
    r.refs.forEach(x=>collect(x,depth+1));
  };
  try {
    collect(name);
    const candidates=[...descendants].filter(([,r])=>state.summaries.has(r.key));
    if (candidates.length!==1) return false;
    const [candidateName,record]=candidates[0], candidate=state.summaries.get(record.key)!;
    const chainNames=new Set([candidateName]);
    for(let i=0;i<9;i++) for(const [n,r] of descendants)
      if ([...r.refs].some(x=>chainNames.has(x))) chainNames.add(n);
    if (!chainNames.has(name) || chainNames.size>6) return false;
    const keys=new Map<string,string>();
    for(const n of chainNames) {
      const r=descendants.get(n)!;
      if (keys.has(r.k) && keys.get(r.k)!==r.key) throw new GReject('polymorphic tree chain');
      keys.set(r.k,r.key);
    }
    state.context={id:name,keys:new Set(keys.values()),candidateKey:record.key,candidate};
    state.clones++;
    let fast:string;
    try { fast=emit_native(fl,ck,ers); }
    finally { state.context=undefined; }
    const original=emitted[1], generic=name+'_tree_generic';
    const sig=sig_def(fl,ck.k);
    const width=sig.lays.flatMap(l=>l.ks).length;
    const decl=sig.lays.flatMap(l=>l.ks).map((k,i)=>`, ${lay_c(k)} r${i}`).join('');
    const renamed=original.replace(new RegExp(`\\b${name}\\b`,'g'),generic);
    emitted[1]=[GL_HOST,
      `/* guarded_tree: typed callback chain; ${chainNames.size} scoped helpers */`,
      renamed,
      `INLINE Term ${name}(Env e, THR Term* o${decl}) {`,
      `  return ${fast}(e, o${Array.from({length:width},(_,i)=>`, r${i}`).join('')});`,
      '}', '#else', original, '#endif'].join('\n');
    emitted[2].add(fast);
    fl.spins.splice(fl.spins.indexOf(emitted),1);
    fl.spins.push(emitted);
    if (process.env.BEND_LOOP_REPORT) fs.appendFileSync(process.env.BEND_LOOP_REPORT,
      JSON.stringify({callee:ck.k,name,fast,tree:true,chain:[...keys.keys()]})+'\n');
    return true;
  } catch(e) {
    if (!(e instanceof GReject)) throw e;
    if (process.env.BEND_GUARDED_TRACE) console.error(`tree reject ${ck.k}: ${e.message}`);
    return false;
  }
}

// Find the callback chain already emitted while compiling a non-flat tree
// definition.  The ordinary compiler has emitted the driver's FID and its
// native callback references by this point, so the same typed call-graph
// proof used by the native-tree path can select exactly one scalar summary.
function gl_tree_context_for_def(fl:File,k:Bend.Name,tld:Def,root:Seg):GLContext|null {
  const state=gl_state(fl);
  if (state.suppress || state.context || state.summaries.size===0
    || !tld.h) return null;
  let call:Call|undefined;
  term_any(fl,tld.h,(t)=>{
    const c=call_kind(fl,t);
    if (c?.k===k) { call=c; return true; }
    return false;
  });
  if (!call || !gl_tree_flat(fl,call) || state.clones>=16) return null;
  const descendants=new Map<string,GLRecord>();
  const collect=(n:string,depth=0):void=>{
    if (depth>8 || descendants.size>24) throw new GReject('tree call graph budget');
    const r=state.records.get(n);
    if (!r || descendants.has(n)) return;
    descendants.set(n,r);
    r.refs.forEach(x=>collect(x,depth+1));
  };
  root.refs.forEach(collect);
  const candidates=[...descendants].filter(([,r])=>state.summaries.has(r.key));
  if (candidates.length!==1) return null;
  const [candidateName,record]=candidates[0], candidate=state.summaries.get(record.key)!;
  const chainNames=new Set([candidateName]);
  for(let i=0;i<9;i++) for(const [n,r] of descendants)
    if ([...r.refs].some(x=>chainNames.has(x))) chainNames.add(n);
  if (chainNames.size>6) return null;
  const keys=new Map<string,string>();
  for(const n of chainNames) {
    const r=descendants.get(n)!;
    if (keys.has(r.k) && keys.get(r.k)!==r.key)
      throw new GReject('polymorphic tree chain');
    keys.set(r.k,r.key);
  }
  // A callback summary whose control tag is the zero test of one returned
  // scalar state word gives the tree driver a typed stop invariant. The
  // emitter uses this only for the concrete control match in this re-emitted
  // FID; generic callers and the fallback FID still inspect the tag itself.
  let control:GLTreeControl|undefined;
  const tag=candidate.outputs.findIndex(x=>x.op==='outzero');
  const left=tag < 0 ? -1 : candidate.outputs[tag].id ?? -1;
  const controlLay=sig_def(fl,k).lays[1];
  if (controlLay !== undefined && tag===0 && left>0 && left<controlLay.ks.length
    && candidate.ret.arms!==null && controlLay.arms!==null
    && lay_eq(candidate.ret,controlLay)
    && controlLay.ks[left]==='w64') {
    control={lay:controlLay,left};
  }
  return {id:root.fid,keys:new Set(keys.values()),candidateKey:record.key,
    candidate,treeK:k,control};
}

// In the scoped tree proof, a returned Control tag is the Boolean zero test
// of the carried scalar counter.  The source driver still has a generic
// Control match; rewrite only its two typed arm conditions to read that
// counter.  The stop arm is identified by its branch shape: it contains no
// call, while the continuing arm must call the already-emitted callback or
// recurse.  If the shape, layout, or tag relation is not exact, the ordinary
// tag test remains in place.
function gl_tree_match_rewrite(fl:File,x:Of<"Mat">,lay:Lay,args:Val[],lv:Level[]):void {
  const cx=gl_state(fl).context, fact=cx?.control;
  if (!fact || cx?.treeK!==fl.def || !lay_eq(lay,fact.lay)
    || args.length===0 || lv.length!==2 || lay.arms===null
    || lay.arms.length!==2 || args[0].ws.length<=fact.left) return;
  const {arms,end}=mat_arms(x);
  if (arms.length!==2 || Bend.term_strip(end).$!=="Efq") return;
  const active=arms.map(([,h])=>term_any(fl,h,t=>call_kind(fl,t)!==null));
  if (active.filter(Boolean).length!==1) return;
  const stop=active.indexOf(false), cont=active.indexOf(true);
  const stopTag=lay.arms.findIndex(a=>a.k===arms[stop][0]);
  const contTag=lay.arms.findIndex(a=>a.k===arms[cont][0]);
  // `outzero` is the Boolean literal 1 for a zero counter.  The typed
  // relation is useful only when that value selects the stopping arm and the
  // other arm is the ordinary zero tag.
  if (stopTag!==1 || contTag!==0) return;
  const left=args[0].ws[fact.left];
  lv[stop][0]=`(${left} == 0)`;
  lv[cont][0]=`(${left} != 0)`;
  if (process.env.BEND_LOOP_REPORT) process.stderr.write(
    JSON.stringify({treeControl:true,def:fl.def,left:fact.left})+'\n');
}

// Compile every definition normally first so the generic FID remains the
// semantic fallback and the callback records are available.  A proven tree
// is then emitted a second time under its callback context.  The resulting
// segment contains a host fast FID and the original FID in the other branch;
// both use the compiler's continuation machinery, so recursive descent never
// becomes a C recursive call.
function gl_compile_def(fl:File,k:Bend.Name,tld:Def,vals:Val[]):void {
  const root=fl.seg;
  emit_body(fl,tld.h as HTerm,tld.T,[],vals,null);
  let cx:GLContext|null=null;
  try { cx=gl_tree_context_for_def(fl,k,tld,root); }
  catch(e) {
    if (!(e instanceof GReject)) throw e;
    if (process.env.BEND_GUARDED_TRACE) console.error(`tree reject ${k}: ${e.message}`);
    return;
  }
  if (!cx) return;
  const rootIndex=fl.segs.indexOf(root);
  if (rootIndex<0) return;
  const genericLines=root.lines.slice(), genericRefs=new Set(root.refs);
  const state=gl_state(fl), old=state.context;
  state.context=cx;
  state.clones++;
  let fastRoot:Seg;
  try {
    const fastVals=emit_open(fl,k);
    fastRoot=fl.seg;
    emit_body(fl,tld.h as HTerm,tld.T,[],fastVals,null);
  } finally {
    state.context=old;
  }
  fastRoot.lines=[GL_HOST,
    `/* guarded_tree: typed callback chain; ${cx.keys.size} scoped helpers */`,
    ...fastRoot.lines, '#else', ...genericLines, '#endif'];
  fastRoot.refs=new Set([...genericRefs,...fastRoot.refs]);
  fastRoot.host=root.host;
  fastRoot.fork=root.fork;
  fl.segs[rootIndex]=fastRoot;
  if (process.env.BEND_LOOP_REPORT) fs.appendFileSync(process.env.BEND_LOOP_REPORT,
    JSON.stringify({callee:k,name:root.fid,fast:fastRoot.fid,tree:true,
      chain:[...cx.keys]})+'\n');
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
  if (GL_ENABLE_TREE && gl_tree_finish(fl,ck,ers,name,emitted)) return;
  const scalar=guarded_scalar(fl,ck,ers,name,original);
  if (!GL_ENABLE_LOOP) {
    if (scalar !== null) emitted[1]=scalar;
    return;
  }
  // Only loops with bounded scalar signatures qualify. Unrelated helpers remain
  // byte-for-byte original in loop mode, including fallback-heavy direct calls.
  const sig=sig_def(fl,ck.k), width=sig.lays.flatMap(l=>l.ks).length;
  const source_box = sig.lays.length > 0 && sig.lays[0].ks.length === 1
    && sig.lays[0].ks[0] === 'box'
    && sig.lays.slice(1).every(l => !l.ks.includes('box'))
    && !sig.ret.ks.includes('box');
  if (width>12 || sig.ret.ks.length>8
    || ([...sig.lays,sig.ret].some(l=>l.ks.includes('box')) && !source_box))
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
    let at=0;
    const trivial:number[]=[], countdownSlots:number[]=[];
    sig.lays.forEach((l,i)=>{
      const slot=at; at+=l.ks.length;
      if (ty_adt(fl.book,sig.live[i][2])?.k === 'Nat' && l.ks.length===1
        && probe.edges.every(e=>{
          const x=e.xs[slot];
          return x.op==='offset' && x.a[0].op==='var' && x.a[0].id===slot && x.a[1].n===-1;
        })) { trivial.push(i); countdownSlots.push(slot); }
    });
    // Optional profitability policy, separate from the safety proof. Select a
    // unique scalar Nat countdown derived from typed back-edge expressions.
    // Multiple countdowns are ambiguous for this policy and keep entry mode.
    const sourceGate=GL_SOURCE_GATE && countdownSlots.length===1 ? countdownSlots[0] : null;
    emitted[1]=[GL_HOST,
      `/* guarded_loop: typed entry guard; ${probe.edges.length} proven back-edge paths; ${chainNames.size} scoped helpers */`,
      original.replace(`${name}(`,`${generic}(`),
      `INLINE Term ${name}(Env e, THR Term* o${decl}) {`,
      ...(sourceGate===null ? [] : [`  if (r${sourceGate} <= 1) return ${generic}(e, o${actual});`]),
      `  if (${guard}) return ${fast}(e, o${actual});`,
      `  return ${generic}(e, o${actual});`,
      '}', `#define ${name}_loop_trivial ${generic}`, '#else',original,
      `#define ${name}_loop_trivial ${name}`, '#endif'].join('\n');
    state.trivial.set(name,{generic:name+'_loop_trivial',doms:trivial});
    emitted[2].add(fast);
    // Native helpers are emitted in dependency order, with no forward prototypes.
    fl.spins.splice(fl.spins.indexOf(emitted),1);
    fl.spins.push(emitted);
    if (process.env.BEND_LOOP_REPORT) fs.appendFileSync(process.env.BEND_LOOP_REPORT,
      JSON.stringify({callee:ck.k,name,fast,guard:probe.guard,backEdges:probe.edges.length,
        chain:[...keys.keys()],width,trivialNatDomains:trivial,sourceGateSlot:sourceGate})+'\n');
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
