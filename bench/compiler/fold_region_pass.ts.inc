// Isolated producer/fold experiment. This is injected into a copy of
// bendlang/main; it is not part of the upstream compiler.
const FOLD_REGION_HELPERS = new WeakMap<object, Map<string, Name>>();
let FOLD_REGION_NEXT = 0;
const FOLD_REGION_STATS: {
  attempts: number;
  fused: number;
  helpers: number;
  rechecked: number;
  refusals: Record<string, number>;
} = { attempts: 0, fused: 0, helpers: 0, rechecked: 0, refusals: {} };
if (process.env.BEND_FOLD_REGION_REPORT) {
  process.on("exit", () => fs.writeFileSync(
    process.env.BEND_FOLD_REGION_REPORT!,
    JSON.stringify(FOLD_REGION_STATS) + "\n"));
}

function fold_region_refuse(reason: string): null {
  FOLD_REGION_STATS.refusals[reason] =
    (FOLD_REGION_STATS.refusals[reason] ?? 0) + 1;
  return null;
}

function fold_region_same(a: HTerm, b: HTerm): boolean {
  return Bend.term_key(Bend.term_lower(term_strip(a)))
    === Bend.term_key(Bend.term_lower(term_strip(b)));
}

function fold_region_var(t: HTerm, p: Probe): boolean {
  const x = term_strip(t);
  return x.$ === "Var" && probe_of(x) === p;
}

function fold_region_apply_lams(t: HTerm, xs: HTerm[]): HTerm | null {
  let out = t;
  for (const x of xs) {
    const f = term_strip(out);
    if (f.$ !== "Lam") return null;
    out = f.f(x);
  }
  return out;
}

function fold_region_rebuild_call(head: HTerm, args: HTerm[],
  result_type: HTerm | null): HTerm {
  const call = args.reduce((f, x) => Bend.App(f, x), head);
  return result_type === null ? call : Bend.Ann(call, result_type);
}

// Only scalar arithmetic/comparison intrinsics are accepted here. This
// prototype deliberately declines array, IO, allocator, and unknown ops.
const FOLD_REGION_PURE_INTRINSICS = new Set([
  "u32_add", "u32_sub", "u32_mul", "u32_div", "u32_mod",
  "u32_and", "u32_or", "u32_xor", "u32_not", "u32_shl", "u32_shr",
  "u32_min", "u32_max", "u32_cmp", "u32_is_eq", "u32_is_ne",
  "u32_is_lt", "u32_is_le", "u32_is_gt", "u32_is_ge",
  "u32_to_nat", "u32_from_nat", "nat_add", "nat_sub", "nat_mul",
  "nat_div", "nat_mod", "nat_cmp", "nat_is_eq", "nat_is_ne",
  "nat_is_lt", "nat_is_le", "nat_is_gt", "nat_is_ge",
  "nat_to_u32", "nat_from_u32", "f32_add", "f32_sub", "f32_mul",
  "f32_div", "f32_mod", "f32_neg", "f32_cmp", "f32_is_eq",
  "f32_is_ne", "f32_is_lt", "f32_is_le", "f32_is_gt", "f32_is_ge",
]);

function fold_region_safe_function(cb: Carb, k: Name,
  seen = new Set<Name>()): boolean {
  const it = intr_of(cb, k, true);
  if (it !== undefined) return FOLD_REGION_PURE_INTRINSICS.has(eff_name(k));
  if (seen.has(k)) return true;
  const raw = cb.book.tlds[k];
  if (raw?.$ !== "Def" || raw.v === null || raw.u || raw.i !== undefined
    || raw.b || raw.x !== 0) return false;
  const def = def_body(cb, k);
  if (def?.$ !== "Def" || def.h === undefined) return false;
  const next = new Set(seen).add(k);
  let safe = true;
  term_any(cb, def.h, (node) => {
    if (node.$ === "Sub" || (node.$ === "Let" && node.k.length > 1)) {
      safe = false;
      return true;
    }
    if (node.$ === "App") {
      const call = term_spine(cb, node);
      if (call.args.length > 0
        && (call.t.$ !== "Ref" || call.call?.bang)) {
        safe = false;
        return true;
      }
    }
    if (node.$ === "Ref") {
      if (node.b || !fold_region_safe_function(cb, node.k, next)) {
        safe = false;
        return true;
      }
    }
    return false;
  });
  return safe;
}

function fold_region_arm(arms: [Name, HTerm][], k: Name): HTerm | null {
  const found = arms.filter(([name]) => name === k);
  return found.length === 1 ? found[0][1] : null;
}

function fold_region_is_empty(arm: HTerm): boolean {
  const x = term_strip(arm);
  return x.$ === "Ctr" && x.k === "Nil" && x.x.length === 0;
}

function fold_region_map_value(cb: Carb, producer_arm: HTerm,
  head: HTerm): HTerm | null {
  const first = term_strip(producer_arm);
  if (first.$ !== "Lam") return null;
  const second = term_strip(first.f(head));
  if (second.$ !== "Lam") return null;
  const ignored_tail = probe("fold_region_ignored_tail");
  const result = term_strip(second.f(ignored_tail));
  if (result.$ !== "Ctr" || result.k !== "Con") return null;
  return ctr_flds(cb.book, result.k, result.x)[0] ?? null;
}

// Rebuild a producer branch from the checked term. Its first constructor
// field is the mapped element and its tail must be the same producer over t.
function fold_region_map_shape(cb: Carb, producer: Def,
  producer_name: Name): { arm: HTerm; callback: Name } | null {
  if (producer.h === undefined) return null;
  const body = term_strip(producer.h);
  if (body.$ !== "Mat") return null;
  const { arms, end } = mat_arms(body);
  const nil = fold_region_arm(arms, "Nil");
  const con = fold_region_arm(arms, "Con");
  if (nil === null || con === null || term_strip(end).$ !== "Efq"
    || !fold_region_is_empty(nil)) return null;
  const head = probe("fold_region_map_head");
  const tail = probe("fold_region_map_tail");
  const built = fold_region_apply_lams(con, [head, tail]);
  if (built === null) return null;
  const node = term_strip(built);
  if (node.$ !== "Ctr" || node.k !== "Con") return null;
  const fields = ctr_flds(cb.book, node.k, node.x);
  if (fields.length !== 2) return null;
  const mapped = term_spine(cb, fields[0]);
  if (mapped.t.$ !== "Ref" || mapped.args.length !== 1
    || !fold_region_var(mapped.args[0], head)
    || !fold_region_safe_function(cb, mapped.t.k)) return null;
  const rest = term_spine(cb, fields[1]);
  if (rest.call?.k !== producer_name || rest.call.bang
    || rest.args.length !== 1
    || !fold_region_var(rest.args[0], tail)) return null;
  return { arm: con, callback: mapped.t.k };
}

function fold_region_rewrap(term: HTerm,
  rewrite: (inner: HTerm) => HTerm): HTerm {
  const x = term_force(term);
  return x.$ === "Ann" ? Bend.Ann(fold_region_rewrap(x.x, rewrite),
    x.T, x.s) : rewrite(x);
}

function fold_region_rewrite_cons_arm(cb: Carb, arm: HTerm,
  consumer_name: Name, helper_name: Name,
  map_value: (head: HTerm) => HTerm): HTerm {
  return fold_region_rewrap(arm, (head_term) => {
    if (head_term.$ !== "Lam") throw new Error("invalid fold region head arm");
    return Bend.Lam(head_term.k, head_term.i, (head) =>
      fold_region_rewrap(head_term.f(head), (tail_term) => {
        if (tail_term.$ !== "Lam") throw new Error("invalid fold region tail arm");
        return Bend.Lam(tail_term.k, tail_term.i, (tail) =>
          fold_region_rewrap(tail_term.f(tail), (state_term) => {
            if (state_term.$ !== "Lam") throw new Error("invalid fold region state arm");
            return Bend.Lam(state_term.k, state_term.i, (state) => {
              const old_call = state_term.f(state);
              const rec = term_spine(cb, old_call);
              if (rec.call?.k !== consumer_name || rec.call.bang
                || rec.args.length !== 2
                || !fold_region_var(rec.args[0], probe_of(tail))) {
                throw new Error("invalid recursive fold region call");
              }
              const old_step = term_spine(cb, rec.args[1]);
              if (old_step.t.$ !== "Ref" || old_step.args.length !== 2
                || !fold_region_var(old_step.args[0], probe_of(state))
                || !fold_region_var(old_step.args[1], probe_of(head))) {
                throw new Error("invalid fold region step");
              }
              const mapped = map_value(head);
              const next_state = fold_region_rebuild_call(old_step.t,
                [state, mapped], ty_ann(rec.args[1]));
              return fold_region_rebuild_call(Bend.Ref(helper_name),
                [tail, next_state], ty_ann(old_call));
            }, state_term.s, state_term.q);
          }), tail_term.s, tail_term.q);
      }), head_term.s, head_term.q);
  });
}

function fold_region_rewrite_match(cb: Carb, body: HTerm,
  consumer_name: Name, helper_name: Name,
  map_value: (head: HTerm) => HTerm): HTerm | null {
  const x = term_force(body);
  if (x.$ === "Ann") {
    const inner = fold_region_rewrite_match(cb, x.x, consumer_name,
      helper_name, map_value);
    return inner === null ? null : Bend.Ann(inner, x.T, x.s);
  }
  if (x.$ !== "Mat") return null;
  const { arms, end } = mat_arms(x);
  const nil = fold_region_arm(arms, "Nil");
  const con = fold_region_arm(arms, "Con");
  if (nil === null || con === null || term_strip(end).$ !== "Efq") return null;
  const state = probe("fold_region_nil_state");
  const nil_result = fold_region_apply_lams(nil, [state]);
  if (nil_result === null || !fold_region_var(nil_result, state)) return null;
  const head = probe("fold_region_fold_head");
  const tail = probe("fold_region_fold_tail");
  const acc = probe("fold_region_fold_state");
  const recur = fold_region_apply_lams(con, [head, tail, acc]);
  if (recur === null) return null;
  const call = term_spine(cb, recur);
  if (call.call?.k !== consumer_name || call.call.bang
    || call.args.length !== 2
    || !fold_region_var(call.args[0], tail)) return null;
  const step = term_spine(cb, call.args[1]);
  if (step.t.$ !== "Ref" || step.args.length !== 2
    || !fold_region_var(step.args[0], acc)
    || !fold_region_var(step.args[1], head)
    || !fold_region_safe_function(cb, step.t.k)) return null;

  const new_con = fold_region_rewrite_cons_arm(cb, con, consumer_name,
    helper_name, map_value);
  const replace = (term: HTerm): HTerm => {
    const node = term_force(term);
    if (node.$ === "Ann") {
      return Bend.Ann(replace(node.x), node.T, node.s);
    }
    if (node.$ !== "Mat") return node;
    const branch = node.k === "Con" ? new_con : node.h;
    return Bend.Mat(node.k, branch, replace(node.m), node.s);
  };
  return replace(body);
}

// A checked consumer body carries type ascriptions for its original input
// list. When the producer changes element type, those ascriptions would pin
// the copied match arms to the producer's output element type. Drop the
// ascriptions and let the synthesized helper's declared type provide the
// source element type; the generated helper is fully checked below.
function fold_region_strip_annotations(term: HTerm): HTerm {
  const x = term_force(term);
  switch (x.$) {
    case "Ann": return fold_region_strip_annotations(x.x);
    case "Var": return x;
    case "Ref": return x;
    case "Sub": {
      const value = x.v.$ === "PVar" || x.v.$ === "PCtr"
        ? x.v : fold_region_strip_annotations(x.v as HTerm);
      return Bend.Sub(x.i, value, fold_region_strip_annotations(x.f), x.s);
    }
    case "App": return Bend.App(fold_region_strip_annotations(x.f),
      fold_region_strip_annotations(x.x), x.s);
    case "Lam": return Bend.Lam(x.k, x.i,
      (arg) => fold_region_strip_annotations(x.f(arg)), x.s, x.q);
    case "Typ": return Bend.Typ(fold_region_strip_annotations(x.g), x.s);
    case "Qnt": return Bend.Qnt(x.s);
    case "Qua": return Bend.Qua(x.q, x.s);
    case "Min": return Bend.Min(fold_region_strip_annotations(x.a),
      fold_region_strip_annotations(x.b), x.s);
    case "All": return Bend.All(x.q, x.k, x.i,
      fold_region_strip_annotations(x.A),
      (arg) => fold_region_strip_annotations(x.B(arg)), x.s);
    case "ADT": return Bend.ADT(x.k, x.x.map(fold_region_strip_annotations),
      x.s, x.r);
    case "Ctr": return Bend.Ctr(x.k, x.x.map(fold_region_strip_annotations), x.s);
    case "Mat": return Bend.Mat(x.k, fold_region_strip_annotations(x.h),
      fold_region_strip_annotations(x.m), x.s);
    case "Let": return Bend.Let(x.k, x.i,
      x.v.map(fold_region_strip_annotations),
      (args) => fold_region_strip_annotations(x.f(args)), x.s, x.q);
    case "Lit": return x;
    case "Efq": return Bend.Efq(x.s);
    case "Eql": return Bend.Eql(fold_region_strip_annotations(x.a),
      fold_region_strip_annotations(x.b),
      fold_region_strip_annotations(x.T), x.s);
    case "Rfl": return Bend.Rfl(x.s);
    case "Rwt": return Bend.Rwt(fold_region_strip_annotations(x.e),
      fold_region_strip_annotations(x.p),
      fold_region_strip_annotations(x.f), x.s);
    case "Hol": return Bend.Hol(x.k, x.s);
  }
}

function fold_region_check_helper(cb: Carb, helper_name: Name,
  template: Def, helper_type: HTerm, body: HTerm): boolean {
  const source = Bend.term_lower(body);
  const provisional = { ...template, T: helper_type, e: undefined,
    v: Bend.term_higher(source) } as Def & { h?: HTerm };
  delete provisional.h;
  cb.book.tlds[helper_name] = provisional;
  try {
    const checked = Bend.def_check(cb.book, helper_name, provisional);
    cb.book.tlds[helper_name] = { ...provisional, e: checked,
      h: Bend.term_higher(checked) };
    FOLD_REGION_STATS.rechecked++;
    return true;
  } catch (_error) {
    delete cb.book.tlds[helper_name];
    return false;
  }
}

function fold_region_helper_type(consumer_type: HTerm,
  source_list_type: HTerm): HTerm | null {
  const type = term_strip(consumer_type);
  if (type.$ !== "All") return null;
  // The fold body is independent of the list's element type. Keep the
  // consumer's quantity and result telescope, but make its source list the
  // producer's input list.
  return Bend.All(type.q, type.k, type.i, source_list_type, type.B, type.s);
}

function fold_region_term(cb: Carb, term: HTerm): HTerm {
  const x = term_force(term);
  const fused = fold_region_try_call(cb, x);
  if (fused !== null) return fused;
  switch (x.$) {
    case "Ann": {
      const inner = fold_region_term(cb, x.x);
      return inner === x.x ? x : Bend.Ann(inner, x.T, x.s);
    }
    case "Lam":
    {
      const opened = term_open(x).b;
      const body = fold_region_term(cb, opened);
      return body === opened ? x : Bend.Lam(x.k, x.i,
        (v: HTerm) => fold_region_term(cb, x.f(v)), x.s, x.q);
    }
    case "App": {
      const f = fold_region_term(cb, x.f);
      const a = fold_region_term(cb, x.x);
      return f === x.f && a === x.x ? x : Bend.App(f, a, x.s);
    }
    case "Ctr": {
      const fields = x.x.map((v) => fold_region_term(cb, v));
      return fields.every((v, i) => v === x.x[i]) ? x
        : Bend.Ctr(x.k, fields, x.s);
    }
    case "Mat": {
      const h = fold_region_term(cb, x.h);
      const m = fold_region_term(cb, x.m);
      return h === x.h && m === x.m ? x : Bend.Mat(x.k, h, m, x.s);
    }
    case "Let": {
      const opened = term_open(x);
      const values = x.v.map((v) => fold_region_term(cb, v));
      const body = fold_region_term(cb, opened.b);
      if (body === opened.b && values.every((v, i) => v === x.v[i])) return x;
      return Bend.Let(x.k, x.i, values,
        (vs: HTerm[]) => fold_region_term(cb, x.f(vs)), x.s, x.q);
    }
    case "Rwt": {
      const f = fold_region_term(cb, x.f);
      return f === x.f ? x : Bend.Rwt(x.e, x.p, f, x.s);
    }
    default: return x;
  }
}

function fold_region_try_call(cb: Carb, term: HTerm): HTerm | null {
  const outer = term_spine(cb, term);
  const consumer_call = outer.call;
  if (consumer_call === null || consumer_call.bang
    || outer.args.length !== 2) return null;
  FOLD_REGION_STATS.attempts++;
  const producer_spine = term_spine(cb, outer.args[0]);
  const producer_call = producer_spine.call;
  if (producer_call === null || producer_call.bang
    || producer_spine.args.length !== 1) {
    return fold_region_refuse("producer-call-shape");
  }
  const source = producer_spine.args[0];
  const init = outer.args[1];
  // The source expression is still evaluated once as the first helper
  // argument. Keep the initial state trivial so moving the producer's work
  // into the helper cannot reorder it past an effect or unsafe computation.
  if (!(term_strip(init).$ === "Var" || term_const(init))) {
    return fold_region_refuse("nontrivial-init");
  }
  const consumer = def_body(cb, consumer_call.k);
  const producer = def_body(cb, producer_call.k);
  if (consumer?.$ !== "Def" || producer?.$ !== "Def"
    || consumer.h === undefined || producer.h === undefined
    || consumer.x !== 0 || producer.x !== 0
    || consumer.n !== 2 || producer.n !== 1) {
    return fold_region_refuse("specialized-def-shape");
  }
  const consumer_type = tele_unbind(cb.book, consumer.T);
  const producer_type = tele_unbind(cb.book, producer.T);
  if (consumer_type.doms.length !== 2 || producer_type.doms.length !== 1
    || ty_adt(cb.book, producer_type.doms[0][2])?.k !== "List"
    || ty_adt(cb.book, producer_type.ret)?.k !== "List"
    || ty_adt(cb.book, consumer_type.doms[0][2])?.k !== "List"
    || !fold_region_same(producer_type.ret, consumer_type.doms[0][2])
    || !fold_region_same(consumer_type.doms[0][2], outer.args[0].$ === "Ann"
      ? ty_ann(outer.args[0])! : producer_type.ret)) {
    return fold_region_refuse("list-type-shape");
  }
  const helper_type = fold_region_helper_type(consumer.T,
    producer_type.doms[0][2]);
  if (helper_type === null) {
    return fold_region_refuse("dependent-fold-type");
  }
  const map_shape = fold_region_map_shape(cb, producer, producer_call.k);
  if (map_shape === null) return fold_region_refuse("producer-body-shape");
  const helper_key = consumer_call.k + "|" + producer_call.k;
  let helpers = FOLD_REGION_HELPERS.get(cb);
  if (helpers === undefined) {
    helpers = new Map();
    FOLD_REGION_HELPERS.set(cb, helpers);
  }
  let helper_name = helpers.get(helper_key);
  if (helper_name === undefined) {
    helper_name = "fold_region_" + FOLD_REGION_NEXT++;
    while (cb.book.tlds[helper_name] !== undefined) {
      helper_name = "fold_region_" + FOLD_REGION_NEXT++;
    }
    const map_value = (head: HTerm): HTerm =>
      fold_region_map_value(cb, map_shape.arm, head)
      ?? die("invalid mapped value in checked fold region");
    const same_element_type = fold_region_same(producer_type.doms[0][2],
      producer_type.ret);
    const consumer_body = same_element_type ? consumer.h
      : fold_region_strip_annotations(consumer.h);
    const helper_body = fold_region_rewrite_match(cb, consumer_body,
      consumer_call.k, helper_name, map_value);
    if (helper_body === null) return fold_region_refuse("consumer-body-shape");
    if (!fold_region_check_helper(cb, helper_name, consumer, helper_type,
      helper_body)) {
      return fold_region_refuse("generated-helper-typecheck");
    }
    helpers.set(helper_key, helper_name);
    FOLD_REGION_STATS.helpers++;
  }
  const result = fold_region_rebuild_call(Bend.Ref(helper_name),
    [source, init], ty_ann(term));
  FOLD_REGION_STATS.fused++;
  return result;
}

function fold_region_rewrite(cb: Carb, body: HTerm): HTerm {
  let found = false;
  term_any(cb, body, (node) => {
    if (found || (node.$ !== "App" && node.$ !== "Ann")) return found;
    const outer = term_spine(cb, node);
    if (outer.call === null || outer.args.length !== 2) return false;
    const producer = term_spine(cb, outer.args[0]);
    found = producer.call !== null && producer.args.length === 1;
    return found;
  });
  if (!found) return body;
  return fold_region_term(cb, body);
}
