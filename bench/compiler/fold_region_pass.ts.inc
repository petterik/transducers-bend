// Isolated producer/fold experiment. This is injected into a copy of
// bendlang/main; it is not part of the upstream compiler.
const FOLD_REGION_HELPERS = new WeakMap<object, Map<string, Name>>();
let FOLD_REGION_NEXT = 0;
const FOLD_REGION_STATS: {
  attempts: number;
  fused: number;
  let_alias_fused: number;
  helpers: number;
  rechecked: number;
  refusals: Record<string, number>;
  region: {
    extracted: number;
    stages: number;
    binds: number;
    branches: number;
    emits: number;
    skips: number;
    refusals: Record<string, number>;
    shapes: Record<string, number>;
  };
} = { attempts: 0, fused: 0, let_alias_fused: 0, helpers: 0, rechecked: 0,
  refusals: {}, region: { extracted: 0, stages: 0, binds: 0, branches: 0,
    emits: 0, skips: 0, refusals: {}, shapes: {} } };

type FoldRegionNode =
  | { tag: "bind"; safety: "pure-total"; id: Probe;
      quantity: HTerm; type: HTerm;
      expr: HTerm; next: FoldRegionNode }
  | { tag: "branch"; safety: "pure-total"; condition: HTerm;
      condition_type: HTerm;
      yes: FoldRegionNode; no: FoldRegionNode }
  | { tag: "emit"; id: Probe }
  | { tag: "skip" };

type FoldRegionStep = {
  producer_name: Name;
  input_id: Probe;
  input_list_type: HTerm;
  output_list_type: HTerm;
  input_quantity: HTerm;
  input_type: HTerm;
  output_quantity: HTerm;
  output_type: HTerm;
  body: FoldRegionNode;
  binds: number;
  branches: number;
  emits: number;
  skips: number;
};

type FoldRegionPipeline = {
  source: HTerm;
  source_type: HTerm;
  source_quantity: HTerm;
  source_element_type: HTerm;
  steps: FoldRegionStep[];
  consumer_step: Name;
  consumer_step_safety: "pure-total";
  accumulator_type: HTerm;
};
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

function fold_region_list_info(book: Bend.Book, list_type: HTerm):
  { quantity: HTerm; element_type: HTerm } | null {
  const list = ty_adt(book, list_type);
  if (list?.k !== "List" || list.x.length < 2) return null;
  return { quantity: list.x[list.x.length - 2],
    element_type: list.x[list.x.length - 1] };
}

function fold_region_total_intrinsic(k: Name, args: HTerm[]): boolean {
  void args;
  const name = eff_name(k);
  if (!FOLD_REGION_PURE_INTRINSICS.has(name)) return false;
  // Bend's U32 division and modulo define zero-divisor results, and its
  // variable shifts guard counts >= 32. Nat add/multiply can reach nat_chk's
  // fail-stop path; refuse those without range proofs.
  if (name === "nat_add" || name === "nat_mul") return false;
  return true;
}

// The old gate rejects many effects but accepts recursive callbacks. A
// fold-step rewrite changes when those calls run relative to the producer, so
// the region requires a conservative totality check in addition to the
// existing effect whitelist.
function fold_region_total_function(cb: Carb, k: Name,
  active = new Set<Name>(), done = new Set<Name>()): boolean {
  const it = intr_of(cb, k, true);
  if (it !== undefined) {
    return fold_region_total_intrinsic(k, []);
  }
  if (active.has(k)) return false;
  if (active.size >= 32) return false;
  if (done.has(k)) return true;
  // Checked Base definitions carry b=true as a library marker. For bounded
  // structural helper expansion that marker is not itself an unsafe effect;
  // the body below still has to pass the same conservative call/effect scan.
  const raw = cb.book.tlds[k];
  if (raw?.$ !== "Def" || raw.v === null || raw.u
    || raw.i !== undefined) return false;
  const def = def_body(cb, k);
  if (def?.$ !== "Def" || def.h === undefined || term_nodes(cb, def.h) > 128) {
    return false;
  }
  const next_active = new Set(active).add(k);
  let total = true;
  term_any(cb, def.h, (node) => {
    if (node.$ === "Sub" || (node.$ === "Let" && node.k.length > 1)) {
      total = false;
      return true;
    }
    if (node.$ === "App") {
      const call = term_spine(cb, node);
      if (call.t.$ === "Ref" && intr_of(cb, call.t.k, true) !== undefined
        && call.args.length > 0) {
        if (!fold_region_total_intrinsic(call.t.k, call.args)) {
          total = false;
          return true;
        }
      } else if (call.call !== null && call.args.length > 0) {
        if (call.t.$ !== "Ref" || call.call.bang) {
          total = false;
          return true;
        }
        if (!fold_region_total_function(cb, call.call.k, next_active, done)) {
          total = false;
          return true;
        }
      }
    }
    if (node.$ === "Ref" && intr_of(cb, node.k, true) === undefined) {
      if (node.b || !fold_region_total_function(cb, node.k,
        next_active, done)) {
        total = false;
        return true;
      }
    }
    return false;
  });
  if (total) done.add(k);
  return total;
}

function fold_region_total_expr(cb: Carb, term: HTerm): boolean {
  let total = true;
  term_any(cb, term, (node) => {
    if (node.$ === "App") {
      const call = term_spine(cb, node);
      if (call.t.$ === "Ref" && intr_of(cb, call.t.k, true) !== undefined
        && call.args.length > 0) {
        if (!fold_region_total_intrinsic(call.t.k, call.args)) {
          const refusals = FOLD_REGION_STATS.region.refusals;
          const key = `region-total-intrinsic:${eff_name(call.t.k)}:args${call.args.length}:${call.args.map((arg) => term_const(arg) ? "const" : "dynamic").join(",")}`;
          refusals[key] = (refusals[key] ?? 0) + 1;
          total = false;
          return true;
        }
      } else if (call.call !== null && call.args.length > 0
        && (!fold_region_safe_function(cb, call.call.k)
          || !fold_region_total_function(cb, call.call.k))) {
        const refusals = FOLD_REGION_STATS.region.refusals;
        const key = "region-total-callback:" + call.call.k;
        refusals[key] = (refusals[key] ?? 0) + 1;
        total = false;
        return true;
      }
    }
    if (node.$ === "Ref") {
      const intr = intr_of(cb, node.k, true) !== undefined;
      if (!intr && (!fold_region_safe_function(cb, node.k)
        || !fold_region_total_function(cb, node.k))) {
        const refusals = FOLD_REGION_STATS.region.refusals;
        const key = "region-total-reference:" + node.k;
        refusals[key] = (refusals[key] ?? 0) + 1;
        total = false;
        return true;
      }
    }
    return false;
  });
  return total;
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
  "u32_to_nat", "u32_from_nat", "u32_shln", "u32_shrn",
  "nat_add", "nat_sub", "nat_mul",
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
  if (seen.size >= 32) return false;
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

function fold_region_recursive_tail(cb: Carb, term: HTerm,
  producer_name: Name, tail: Probe): boolean {
  const call = term_spine(cb, term);
  return call.call?.k === producer_name && !call.call.bang
    && call.args.length === 1 && fold_region_var(call.args[0], tail);
}

function fold_region_has_recursive_call(cb: Carb, term: HTerm,
  producer_name: Name): boolean {
  let found = false;
  term_any(cb, term, (node) => {
    if (node.$ !== "App") return false;
    const call = term_spine(cb, node);
    found = call.call?.k === producer_name;
    return found;
  });
  return found;
}

function fold_region_emit_node(expr: HTerm, output_quantity: HTerm,
  output_type: HTerm): FoldRegionNode {
  const id = probe("fold_region_emitted_value");
  return { tag: "bind", safety: "pure-total", id, quantity: output_quantity,
    type: output_type, expr,
    next: { tag: "emit", id } };
}

function fold_region_analysis_refuse(reason: string): null {
  const refusals = FOLD_REGION_STATS.region.refusals;
  refusals[reason] = (refusals[reason] ?? 0) + 1;
  return null;
}

function fold_region_applied_match(cb: Carb, term: HTerm):
  { match: HTerm; condition: HTerm } | null {
  const spine = term_spine(cb, term);
  const match = term_force(spine.t);
  return match.$ === "Mat" && spine.all.length === 1
    ? { match, condition: spine.all[0] } : null;
}

function fold_region_parse_step_result(cb: Carb, term: HTerm,
  producer_name: Name, tail: Probe, output_quantity: HTerm,
  output_type: HTerm,
  fuel: { depth: number; nodes: number }): FoldRegionNode | null {
  if (--fuel.nodes < 0) return fold_region_analysis_refuse("region-node-budget");
  const value = term_strip(term);
  if (fold_region_recursive_tail(cb, value, producer_name, tail)) {
    return { tag: "skip" };
  }
  if (value.$ === "Ctr" && value.k === "Con") {
    const fields = ctr_flds(cb.book, value.k, value.x);
    if (fields.length !== 2
      || !fold_region_recursive_tail(cb, fields[1], producer_name, tail)
      || fold_region_has_recursive_call(cb, fields[0], producer_name)
      || !fold_region_total_expr(cb, fields[0])) {
      return fold_region_analysis_refuse("region-emit-shape-or-totality");
    }
    return fold_region_emit_node(fields[0], output_quantity, output_type);
  }
  const applied_match = fold_region_applied_match(cb, value);
  if (applied_match !== null) {
    const { match, condition } = applied_match;
    const { arms, end } = mat_arms(match);
    const no = fold_region_arm(arms, "False");
    const yes = fold_region_arm(arms, "True");
    const condition_type = ty_adt(cb.book, ty_ann(condition));
    if (arms.length !== 2 || no === null || yes === null
      || term_strip(end).$ !== "Efq") {
      return fold_region_analysis_refuse("region-branch-shape");
    }
    if (condition_type?.k !== "Bool") {
      return fold_region_analysis_refuse("region-condition-type");
    }
    if (fold_region_has_recursive_call(cb, condition, producer_name)) {
      return fold_region_analysis_refuse("region-condition-recursive");
    }
    if (!fold_region_total_expr(cb, condition)) {
      return fold_region_analysis_refuse("region-condition-not-total");
    }
    const no_region = fold_region_parse_step_result(cb, no,
      producer_name, tail, output_quantity, output_type, fuel);
    const yes_region = fold_region_parse_step_result(cb, yes,
      producer_name, tail, output_quantity, output_type, fuel);
    return no_region === null || yes_region === null
      ? fold_region_analysis_refuse("region-branch-exit-shape")
      : { tag: "branch", safety: "pure-total", condition,
        condition_type: ty_ann(condition)!, yes: yes_region, no: no_region };
  }

  // A small, checked, non-recursive helper may hide a branch that selects
  // between the recursive tail and a constructor. Expose its weak-head form
  // generically; never inline the producer's own recursive call here.
  if (fuel.depth >= 8) return fold_region_analysis_refuse("region-inline-depth");
  const spine = term_spine(cb, value);
  if (spine.call === null) return fold_region_analysis_refuse("region-helper-not-static-call");
  if (spine.call.k === producer_name) return fold_region_analysis_refuse("region-unexpected-recursive-call");
  if (spine.args.length === 0) return fold_region_analysis_refuse("region-helper-unsaturated");
  if (!fold_region_total_function(cb, spine.call.k)) {
    return fold_region_analysis_refuse("region-helper-not-total-static-call:" + spine.call.k);
  }
  const helper = def_body(cb, spine.call.k);
  if (helper?.$ !== "Def" || helper.h === undefined
    || term_nodes(cb, helper.h) > 128 || helper.v === null
    || spine.all.length !== helper.n) {
    return fold_region_analysis_refuse("region-helper-size");
  }
  // WNF deliberately preserves a stuck match call as its original reference.
  // Apply the checked helper body to its full typed argument spine instead;
  // this exposes a Mat applied to an unknown Bool without guessing its arm.
  const expanded = spine.all.reduce<HTerm>((body, arg) =>
    Bend.term_apply(body, arg), helper.v);
  if (term_nodes(cb, expanded) > 128) {
    return fold_region_analysis_refuse("region-inline-node-budget");
  }
  return fold_region_parse_step_result(cb, expanded, producer_name, tail,
    output_quantity, output_type,
    { depth: fuel.depth + 1, nodes: fuel.nodes });
}

function fold_region_measure(node: FoldRegionNode): {
  binds: number; branches: number; emits: number; skips: number;
} {
  switch (node.tag) {
    case "skip": return { binds: 0, branches: 0, emits: 0, skips: 1 };
    case "emit": return { binds: 0, branches: 0, emits: 1, skips: 0 };
    case "bind": {
      const next = fold_region_measure(node.next);
      return { ...next, binds: next.binds + 1 };
    }
    case "branch": {
      const yes = fold_region_measure(node.yes);
      const no = fold_region_measure(node.no);
      return {
        binds: yes.binds + no.binds,
        branches: yes.branches + no.branches + 1,
        emits: yes.emits + no.emits,
        skips: yes.skips + no.skips,
      };
    }
  }
}

function fold_region_build_step(cb: Carb, producer: Def,
  producer_name: Name): FoldRegionStep | null {
  if (producer.h === undefined) return fold_region_analysis_refuse("region-missing-body");
  const type = tele_unbind(cb.book, producer.T);
  if (type.doms.length !== 1) return fold_region_analysis_refuse("region-producer-arity");
  const input_list_type = type.doms[0][2];
  const output_list_type = type.ret;
  const input_info = fold_region_list_info(cb.book, input_list_type);
  const output_info = fold_region_list_info(cb.book, output_list_type);
  if (input_info === null || output_info === null) {
    return fold_region_analysis_refuse("region-producer-not-list-shaped");
  }

  const body = term_strip(producer.h);
  if (body.$ !== "Mat") return fold_region_analysis_refuse("region-producer-not-match");
  const { arms, end } = mat_arms(body);
  const nil = fold_region_arm(arms, "Nil");
  const con = fold_region_arm(arms, "Con");
  if (nil === null || con === null || term_strip(end).$ !== "Efq"
    || !fold_region_is_empty(nil)) {
    return fold_region_analysis_refuse("region-producer-empty-or-cons-arm");
  }
  const head = probe("fold_region_step_input");
  const tail = probe("fold_region_step_tail");
  const result = fold_region_apply_lams(con, [head, tail]);
  if (result === null) return fold_region_analysis_refuse("region-producer-arm-lambda");
  const graph = fold_region_parse_step_result(cb, result, producer_name,
    tail, output_info.quantity, output_info.element_type,
    { depth: 0, nodes: 64 });
  if (graph === null) return fold_region_analysis_refuse("region-step-result");
  const counts = fold_region_measure(graph);
  if (counts.emits === 0 || counts.emits > 16 || counts.skips > 16
    || counts.branches > 16 || term_nodes(cb, result) > 128) {
    return fold_region_analysis_refuse("region-step-output-budget");
  }
  return { producer_name, input_id: head, input_list_type, output_list_type,
    input_quantity: input_info.quantity, input_type: input_info.element_type,
    output_quantity: output_info.quantity,
    output_type: output_info.element_type, body: graph, ...counts };
}

function fold_region_full_fold_step(cb: Carb, consumer: Def,
  consumer_name: Name): Name | null {
  if (consumer.h === undefined) return null;
  const body = term_strip(consumer.h);
  if (body.$ !== "Mat") return null;
  const { arms, end } = mat_arms(body);
  const nil = fold_region_arm(arms, "Nil");
  const con = fold_region_arm(arms, "Con");
  if (nil === null || con === null || term_strip(end).$ !== "Efq") return null;
  const state0 = probe("fold_region_region_nil_state");
  const nil_result = fold_region_apply_lams(nil, [state0]);
  if (nil_result === null || !fold_region_var(nil_result, state0)) return null;
  const head = probe("fold_region_region_fold_head");
  const tail = probe("fold_region_region_fold_tail");
  const state = probe("fold_region_region_fold_state");
  const recur = fold_region_apply_lams(con, [head, tail, state]);
  if (recur === null) return null;
  const call = term_spine(cb, recur);
  if (call.call?.k !== consumer_name || call.call.bang
    || call.args.length !== 2 || !fold_region_var(call.args[0], tail)) return null;
  const step = term_spine(cb, call.args[1]);
  if (step.t.$ !== "Ref" || step.args.length !== 2
    || !fold_region_var(step.args[0], state)
    || !fold_region_var(step.args[1], head)
    || !fold_region_safe_function(cb, step.t.k)
    || !fold_region_total_function(cb, step.t.k)) return null;
  return step.t.k;
}

function fold_region_analyze_pipeline(cb: Carb, consumer: Def,
  consumer_name: Name, producer: Def, producer_name: Name,
  source: HTerm): FoldRegionPipeline | null {
  const consumer_step = fold_region_full_fold_step(cb, consumer, consumer_name);
  if (consumer_step === null) {
    FOLD_REGION_STATS.region.refusals["consumer-not-total-full-fold"] =
      (FOLD_REGION_STATS.region.refusals["consumer-not-total-full-fold"] ?? 0) + 1;
    return null;
  }
  const seen = new Set<Name>();
  const steps: FoldRegionStep[] = [];
  let current = producer;
  let current_name = producer_name;
  let current_source = source;
  let source_type: HTerm | null = null;
  let expected_input: HTerm | null = null;
  for (let depth = 0; depth < 8; depth++) {
    if (seen.has(current_name)) {
      FOLD_REGION_STATS.region.refusals["producer-call-cycle"] =
        (FOLD_REGION_STATS.region.refusals["producer-call-cycle"] ?? 0) + 1;
      return null;
    }
    seen.add(current_name);
    const step = fold_region_build_step(cb, current, current_name);
    if (step === null) {
      FOLD_REGION_STATS.region.refusals["producer-step-shape"] =
        (FOLD_REGION_STATS.region.refusals["producer-step-shape"] ?? 0) + 1;
      return null;
    }
    const current_type = tele_unbind(cb.book, current.T);
    const input_list_type = current_type.doms[0][2];
    if (expected_input !== null
      && !fold_region_same(current_type.ret, expected_input)) {
      FOLD_REGION_STATS.region.refusals["producer-stage-type-edge"] =
        (FOLD_REGION_STATS.region.refusals["producer-stage-type-edge"] ?? 0) + 1;
      return null;
    }
    source_type = input_list_type;
    expected_input = input_list_type;
    steps.unshift(step);

    const inner = term_spine(cb, current_source);
    if (inner.call === null || inner.call.bang || inner.args.length !== 1) {
      break;
    }
    const inner_def = def_body(cb, inner.call.k);
    if (inner_def?.$ !== "Def" || inner_def.h === undefined
      || inner_def.n !== 1) break;
    const inner_type = tele_unbind(cb.book, inner_def.T);
    if (inner_type.doms.length !== 1
      || ty_adt(cb.book, inner_type.doms[0][2])?.k !== "List"
      || ty_adt(cb.book, inner_type.ret)?.k !== "List"
      || !fold_region_same(inner_type.ret, input_list_type)) break;
    current = inner_def;
    current_name = inner.call.k;
    current_source = inner.args[0];
  }
  if (source_type === null || expected_input === null || steps.length === 0) {
    return null;
  }
  const source_info = fold_region_list_info(cb.book, source_type);
  if (source_info === null) return null;
  for (let i = 1; i < steps.length; i++) {
    if (!fold_region_same(steps[i - 1].output_type, steps[i].input_type)) {
      FOLD_REGION_STATS.region.refusals["producer-stage-element-type"] =
        (FOLD_REGION_STATS.region.refusals["producer-stage-element-type"] ?? 0) + 1;
      return null;
    }
    if (!fold_region_same(steps[i - 1].output_quantity,
      steps[i].input_quantity)) {
      FOLD_REGION_STATS.region.refusals["producer-stage-quantity-edge"] =
        (FOLD_REGION_STATS.region.refusals["producer-stage-quantity-edge"] ?? 0) + 1;
      return null;
    }
  }
  const consumer_type = tele_unbind(cb.book, consumer.T);
  const accumulator_type = consumer_type.doms[1]?.[2];
  const consumer_input = fold_region_list_info(cb.book,
    consumer_type.doms[0]?.[2] ?? null);
  if (accumulator_type === undefined || consumer_input === null
    || !fold_region_same(steps[steps.length - 1].output_type,
      consumer_input.element_type)
    || !fold_region_same(steps[steps.length - 1].output_quantity,
      consumer_input.quantity)) {
    FOLD_REGION_STATS.region.refusals["fold-element-type"] =
      (FOLD_REGION_STATS.region.refusals["fold-element-type"] ?? 0) + 1;
    return null;
  }
  return { source: current_source, source_type: source_type,
    source_quantity: source_info.quantity,
    source_element_type: source_info.element_type, steps, consumer_step,
    consumer_step_safety: "pure-total", accumulator_type };
}

function fold_region_record_pipeline(pipeline: FoldRegionPipeline): void {
  const stats = FOLD_REGION_STATS.region;
  stats.extracted++;
  stats.stages += pipeline.steps.length;
  stats.binds += pipeline.steps.reduce((n, step) => n + step.binds, 0);
  stats.branches += pipeline.steps.reduce((n, step) => n + step.branches, 0);
  stats.emits += pipeline.steps.reduce((n, step) => n + step.emits, 0);
  stats.skips += pipeline.steps.reduce((n, step) => n + step.skips, 0);
  const shape = pipeline.steps.map((step) =>
    `${step.binds}:${step.branches}:${step.emits}:${step.skips}`).join(">");
  stats.shapes[shape] = (stats.shapes[shape] ?? 0) + 1;
}

function fold_region_rewrap(term: HTerm,
  rewrite: (inner: HTerm) => HTerm): HTerm {
  const x = term_force(term);
  return x.$ === "Ann" ? Bend.Ann(fold_region_rewrap(x.x, rewrite),
    x.T, x.s) : rewrite(x);
}

// Substitute the stable identities kept by the analyzed region. Use Bend's
// HOAS callbacks when rebuilding binders, so replacing a producer input under
// a match, lambda, or local cannot capture an unrelated value.
function fold_region_substitute(term: HTerm,
  values: Map<number, HTerm>): HTerm {
  const x = term_force(term);
  switch (x.$) {
    case "Var": return values.get(x.i) ?? x;
    case "Ref": case "Lit": case "Qnt": case "Qua": case "Efq": case "Rfl":
    case "Hol": return x;
    case "Ann": return Bend.Ann(fold_region_substitute(x.x, values),
      fold_region_substitute(x.T, values), x.s);
    case "Sub": {
      const value = x.v.$ === "PVar" || x.v.$ === "PCtr"
        ? x.v : fold_region_substitute(x.v as HTerm, values);
      return Bend.Sub(x.i, value, fold_region_substitute(x.f, values), x.s);
    }
    case "Typ": return Bend.Typ(fold_region_substitute(x.g, values), x.s);
    case "Min": return Bend.Min(fold_region_substitute(x.a, values),
      fold_region_substitute(x.b, values), x.s);
    case "All": return Bend.All(x.q, x.k, x.i,
      fold_region_substitute(x.A, values),
      (arg: HTerm) => fold_region_substitute(x.B(arg), values), x.s);
    case "Lam": return Bend.Lam(x.k, x.i,
      (arg: HTerm) => fold_region_substitute(x.f(arg), values), x.s, x.q);
    case "App": return Bend.App(fold_region_substitute(x.f, values),
      fold_region_substitute(x.x, values), x.s);
    case "ADT": return Bend.ADT(x.k, x.x.map((v) =>
      fold_region_substitute(v, values)), x.s, x.r);
    case "Ctr": return Bend.Ctr(x.k, x.x.map((v) =>
      fold_region_substitute(v, values)), x.s);
    case "Mat": return Bend.Mat(x.k, fold_region_substitute(x.h, values),
      fold_region_substitute(x.m, values), x.s);
    case "Let": return Bend.Let(x.k, x.i, x.v.map((v) =>
      fold_region_substitute(v, values)),
      (args: HTerm[]) => fold_region_substitute(x.f(args), values), x.s, x.q);
    case "Eql": return Bend.Eql(fold_region_substitute(x.a, values),
      fold_region_substitute(x.b, values),
      fold_region_substitute(x.T, values), x.s);
    case "Rwt": return Bend.Rwt(fold_region_substitute(x.e, values),
      fold_region_substitute(x.p, values),
      fold_region_substitute(x.f, values), x.s);
  }
}

function fold_region_quantity(qty: HTerm): Bend.Quant | null {
  const value = term_strip(qty);
  if (value.$ === "Qua") return value.q;
  if (value.$ === "Qnt") return Bend.None();
  return null;
}

type FoldRegionEmit = (value: HTerm) => HTerm;
type FoldRegionSkip = () => HTerm;

function fold_region_lower_node(node: FoldRegionNode,
  values: Map<number, HTerm>, emit: FoldRegionEmit,
  skip: FoldRegionSkip, match_result_type: HTerm): HTerm {
  switch (node.tag) {
    case "skip": return skip();
    case "emit": {
      const value = values.get(node.id.i);
      if (value === undefined) {
        throw new Error("fold region emitted an unbound value");
      }
      return emit(value);
    }
    case "bind": {
      const quant = fold_region_quantity(
        fold_region_substitute(node.quantity, values));
      if (quant === null) {
        throw new Error("fold region has an unknown binder quantity");
      }
      const expression = fold_region_substitute(node.expr, values);
      const type = fold_region_substitute(node.type, values);
      return Bend.Let([node.id.k], [0], [Bend.Ann(expression, type)],
        (args: HTerm[]) => {
          if (args.length !== 1) {
            throw new Error("fold region Let opened with wrong arity");
          }
          const next = new Map(values);
          next.set(node.id.i, args[0]);
          return fold_region_lower_node(node.next, next, emit, skip,
            match_result_type);
        }, undefined, [quant]);
    }
    case "branch": {
      const yes = fold_region_lower_node(node.yes, new Map(values), emit,
        skip, match_result_type);
      const no = fold_region_lower_node(node.no, new Map(values), emit,
        skip, match_result_type);
      const condition = Bend.Ann(
        fold_region_substitute(node.condition, values),
        fold_region_substitute(node.condition_type, values));
      const match = Bend.Mat("True", yes,
        Bend.Mat("False", no, Bend.Efq()));
      const match_type = Bend.All(Bend.Lone(), "fold_region_condition", 0,
        fold_region_substitute(node.condition_type, values),
        () => match_result_type);
      return Bend.App(Bend.Ann(match, match_type), condition);
    }
  }
}

function fold_region_lower_cost(cb: Carb, steps: FoldRegionStep[],
  index: number, cap: number): number {
  const add = (...parts: number[]): number =>
    Math.min(cap + 1, parts.reduce((sum, part) => sum + part, 0));
  const next = (): number => index + 1 >= steps.length
    ? 8 : fold_region_lower_cost(cb, steps, index + 1, cap);
  const measure = (node: FoldRegionNode): number => {
    switch (node.tag) {
      case "skip": return 8;
      case "emit": return next();
      case "bind": return add(8, term_nodes(cb, node.expr),
        term_nodes(cb, node.type), measure(node.next));
      case "branch": return add(12, term_nodes(cb, node.condition),
        term_nodes(cb, node.condition_type), measure(node.yes),
        measure(node.no));
    }
  };
  return steps[index] === undefined ? 0 : measure(steps[index].body);
}

function fold_region_lower_pipeline(cb: Carb, pipeline: FoldRegionPipeline,
  helper_name: Name, source_head: HTerm, tail: HTerm, state: HTerm,
  result_type: HTerm | null): HTerm | null {
  if (fold_region_lower_cost(cb, pipeline.steps, 0, 2048) > 2048) {
    return null;
  }
  const recurse = (next_state: HTerm): HTerm =>
    fold_region_rebuild_call(Bend.Ref(helper_name), [tail, next_state],
      result_type);
  const lower_stage = (index: number, input: HTerm): HTerm | null => {
    if (index >= pipeline.steps.length) {
      const next_state = fold_region_rebuild_call(
        Bend.Ref(pipeline.consumer_step), [state, input],
        pipeline.accumulator_type);
      return recurse(next_state);
    }
    const stage = pipeline.steps[index];
    const values = new Map<number, HTerm>([[stage.input_id.i, input]]);
    return fold_region_lower_node(stage.body, values,
      (output) => lower_stage(index + 1, output)
        ?? (() => { throw new Error("fold region exceeded lowering budget"); })(),
      () => recurse(state), pipeline.accumulator_type);
  };
  return lower_stage(0, source_head);
}

function fold_region_rewrite_region_cons_arm(cb: Carb, arm: HTerm,
  consumer_name: Name, helper_name: Name,
  pipeline: FoldRegionPipeline): HTerm | null {
  let failed = false;
  const rewritten = fold_region_rewrap(arm, (head_term) => {
    if (head_term.$ !== "Lam") { failed = true; return head_term; }
    return Bend.Lam(head_term.k, head_term.i, (head) =>
      fold_region_rewrap(head_term.f(head), (tail_term) => {
        if (tail_term.$ !== "Lam") { failed = true; return tail_term; }
        return Bend.Lam(tail_term.k, tail_term.i, (tail) =>
          fold_region_rewrap(tail_term.f(tail), (state_term) => {
            if (state_term.$ !== "Lam") { failed = true; return state_term; }
            return Bend.Lam(state_term.k, state_term.i, (state) => {
              const old_call = state_term.f(state);
              const rec = term_spine(cb, old_call);
              if (rec.call?.k !== consumer_name || rec.call.bang
                || rec.args.length !== 2
                || !fold_region_var(rec.args[0], probe_of(tail))) {
                failed = true;
                return old_call;
              }
              const old_step = term_spine(cb, rec.args[1]);
              if (old_step.t.$ !== "Ref" || old_step.args.length !== 2
                || !fold_region_var(old_step.args[0], probe_of(state))
                || !fold_region_var(old_step.args[1], probe_of(head))) {
                failed = true;
                return old_call;
              }
              return fold_region_lower_pipeline(cb, pipeline, helper_name, head,
                tail, state, ty_ann(old_call)) ?? (failed = true, old_call);
            }, state_term.s, state_term.q);
          }), tail_term.s, tail_term.q);
      }), head_term.s, head_term.q);
  });
  return failed ? null : rewritten;
}

function fold_region_rewrite_region_match(cb: Carb, body: HTerm,
  consumer_name: Name, helper_name: Name,
  pipeline: FoldRegionPipeline): HTerm | null {
  const x = term_force(body);
  if (x.$ === "Ann") {
    const inner = fold_region_rewrite_region_match(cb, x.x, consumer_name,
      helper_name, pipeline);
    return inner === null ? null : Bend.Ann(inner, x.T, x.s);
  }
  if (x.$ !== "Mat") return null;
  const { arms, end } = mat_arms(x);
  const nil = fold_region_arm(arms, "Nil");
  const con = fold_region_arm(arms, "Con");
  if (nil === null || con === null || term_strip(end).$ !== "Efq") return null;
  const state = probe("fold_region_region_nil_state");
  const nil_result = fold_region_apply_lams(nil, [state]);
  if (nil_result === null || !fold_region_var(nil_result, state)) return null;
  const head = probe("fold_region_region_head");
  const tail = probe("fold_region_region_tail");
  const acc = probe("fold_region_region_acc");
  const recur = fold_region_apply_lams(con, [head, tail, acc]);
  if (recur === null) return null;
  const call = term_spine(cb, recur);
  if (call.call?.k !== consumer_name || call.call.bang
    || call.args.length !== 2 || !fold_region_var(call.args[0], tail)) return null;
  const step = term_spine(cb, call.args[1]);
  if (step.t.$ !== "Ref" || step.args.length !== 2
    || !fold_region_var(step.args[0], acc)
    || !fold_region_var(step.args[1], head)) return null;

  const new_con = fold_region_rewrite_region_cons_arm(cb, con,
    consumer_name, helper_name, pipeline);
  if (new_con === null) return null;
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
  } catch (error) {
    if (process.env.BEND_FOLD_REGION_DEBUG) console.error(error);
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
      const single_use = fold_region_try_single_use_let(cb, x);
      if (single_use !== null) return single_use;
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

// Follow a producer through a local only when the entire let is a single
// binding, its body immediately folds that binding, and the binding has one
// use. The call rewrite then preserves the let's evaluation point and the
// normal helper checker proves the moved value is affine-safe.
function fold_region_try_single_use_let(cb: Carb, term: HLet): HTerm | null {
  if (term.k.length !== 1 || term.v.length !== 1) return null;
  const opened = term_open(term);
  const p = opened.ps[0];
  const outer = term_spine(cb, opened.b);
  const consumer = outer.call;
  if (consumer === null || consumer.bang || outer.args.length !== 2
    || !fold_region_var(outer.args[0], p)) return null;
  if (term_use(term_uses(cb, opened.b), p) !== 1) {
    return fold_region_refuse("let-bound-use-count");
  }
  const candidate = fold_region_rebuild_call(Bend.Ref(consumer.k),
    [term.v[0], outer.args[1]], ty_ann(opened.b));
  const fused = fold_region_try_call(cb, candidate);
  if (fused !== null) FOLD_REGION_STATS.let_alias_fused++;
  return fused;
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
  const pipeline = fold_region_analyze_pipeline(cb, consumer,
    consumer_call.k, producer, producer_call.k, source);
  if (pipeline === null) {
    return fold_region_refuse("producer-step-analysis");
  }
  const helper_type = fold_region_helper_type(consumer.T,
    pipeline.source_type);
  if (helper_type === null) {
    return fold_region_refuse("dependent-fold-type");
  }
  fold_region_record_pipeline(pipeline);
  const has_skip = pipeline.steps.some((step) => step.skips > 0);
  const map_shape = has_skip ? null
    : fold_region_map_shape(cb, producer, producer_call.k);
  if (!has_skip && map_shape === null) {
    return fold_region_refuse("producer-body-shape");
  }
  const helper_key = consumer_call.k + "|" + pipeline.steps
    .map((step) => step.producer_name).join("|");
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
    const same_element_type = fold_region_same(pipeline.source_type,
      consumer_type.doms[0][2]);
    const consumer_body = same_element_type ? consumer.h
      : fold_region_strip_annotations(consumer.h);
    const helper_body = has_skip
      ? fold_region_rewrite_region_match(cb, consumer_body,
        consumer_call.k, helper_name, pipeline)
      : fold_region_rewrite_match(cb, consumer_body,
        consumer_call.k, helper_name, (head: HTerm) =>
          fold_region_map_value(cb, map_shape!.arm, head)
            ?? die("invalid mapped value in checked fold region"));
    if (helper_body === null) return fold_region_refuse("consumer-body-shape");
    if (term_nodes(cb, helper_body) > 2048) {
      return fold_region_refuse("generated-helper-node-budget");
    }
    if (!fold_region_check_helper(cb, helper_name, consumer, helper_type,
      helper_body)) {
      return fold_region_refuse("generated-helper-typecheck");
    }
    helpers.set(helper_key, helper_name);
    FOLD_REGION_STATS.helpers++;
  }
  const result = fold_region_rebuild_call(Bend.Ref(helper_name),
    [pipeline.source, init], ty_ann(term));
  FOLD_REGION_STATS.fused++;
  return result;
}

function fold_region_rewrite(cb: Carb, body: HTerm): HTerm {
  let found = false;
  term_any(cb, body, (node) => {
    if (found) return true;
    if (node.$ === "Let" && node.k.length === 1 && node.v.length === 1) {
      const opened = term_open(node);
      const consumer = term_spine(cb, opened.b);
      if (consumer.call !== null && !consumer.call.bang
        && consumer.args.length === 2
        && fold_region_var(consumer.args[0], opened.ps[0])) {
        const producer = term_spine(cb, node.v[0]);
        if (producer.call !== null && !producer.call.bang
          && producer.args.length === 1) {
          found = true;
          return true;
        }
      }
    }
    if (node.$ !== "App" && node.$ !== "Ann") return false;
    const outer = term_spine(cb, node);
    if (outer.call === null || outer.args.length !== 2) return false;
    const producer = term_spine(cb, outer.args[0]);
    found = producer.call !== null && producer.args.length === 1;
    return found;
  });
  if (!found) return body;
  return fold_region_term(cb, body);
}
