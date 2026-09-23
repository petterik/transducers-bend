function static_identity_test_assert(ok: boolean, label: string): void {
  if (!ok) throw new Error("static identity self-test: " + label);
}
function static_identity_test_instance(name: Bend.Name): TLD {
  return { $: "Def", n: 0, x: 0,
    e: Bend.Ref(name), v: Bend.Ref(name) } as TLD;
}
function static_identity_test_book(generic: Bend.Name,
  entries: Array<[HTerm, Bend.Name]>): Book {
  const tlds = Object.create(null) as Record<string, TLD>;
  const table = Object.create(null) as Record<string, Bend.Name>;
  tlds[generic] = { $: "Def", n: 0, x: 1,
    e: Bend.Ref(generic), v: Bend.Ref(generic) } as TLD;
  const names = new Set(entries.map(([, name]) => name));
  for (const name of names) tlds[name] = static_identity_test_instance(name);
  for (const [term, name] of entries) {
    table[Bend.term_key(Bend.term_lower(term))] = name;
  }
  const tmps = Object.create(null) as Record<string, Record<string, Bend.Name>>;
  tmps[generic] = table;
  return { tlds, tmps } as unknown as Book;
}
function static_identity_test_body(value: Bend.Name): HTerm {
  return Bend.Lam("x" as Bend.Name, 0, (_x: HTerm) => Bend.Ref(value));
}
function static_identity_self_test(): void {
  const generic = "StaticIdentity.generic" as Bend.Name;
  const first = "StaticIdentity.first" as Bend.Name;
  const second = "StaticIdentity.second" as Bend.Name;
  const base = Bend.Ref("StaticIdentity.argument" as Bend.Name);
  const type1 = Bend.Ref("StaticIdentity.type1" as Bend.Name);
  const type2 = Bend.Ref("StaticIdentity.type2" as Bend.Name);
  const type3 = Bend.Ref("StaticIdentity.type3" as Bend.Name);
  const annotated = Bend.Ann(base, type1);
  let book = static_identity_test_book(generic, [[base, first]]);
  static_identity_test_assert(
    static_template_instance(book, generic, [annotated]) === first,
    "annotation-only checked key resolves its existing instance");
  const lambda_default = Bend.term_lower(Bend.Lam("x" as Bend.Name, 0,
    (x: HTerm) => x));
  const lambda_checked = Bend.term_lower(Bend.Lam("x" as Bend.Name, 0,
    (x: HTerm) => x, undefined, Bend.Lone()));
  static_identity_test_assert(
    static_template_key(lambda_default) === static_template_key(lambda_checked),
    "source and checked lambdas share their default multiplicity key");

  const aliasA = "StaticIdentity.alias_a" as Bend.Name;
  const aliasB = "StaticIdentity.alias_b" as Bend.Name;
  const shared = Bend.Ref("StaticIdentity.shared" as Bend.Name);
  book = static_identity_test_book(generic, [[Bend.Ref(aliasA), first]]);
  const tlds = book.tlds as Record<string, TLD>;
  tlds[aliasA] = { $: "Def", n: 0, x: 0, e: shared, v: shared } as TLD;
  tlds[aliasB] = { $: "Def", n: 0, x: 0, e: shared, v: shared } as TLD;
  static_identity_test_assert(
    static_template_instance(book, generic, [Bend.Ref(aliasB)]) === null,
    "conversion-equal aliases do not select another source-syntax instance");

  const ann1 = Bend.Ann(base, type1);
  const ann2 = Bend.Ann(base, type2);
  const ann3 = Bend.Ann(base, type3);
  book = static_identity_test_book(generic, [[ann1, first], [ann2, second]]);
  static_identity_test_assert(
    static_template_instance(book, generic, [ann3]) === null,
    "two normalized matches are ambiguous and refuse specialization");

  book = static_identity_test_book(generic, [[base, first], [ann1, second]]);
  static_identity_test_assert(
    static_template_instance(book, generic, [ann2]) === null,
    "normalized direct-key hits cannot hide another structurally equal entry");

  const loop = "StaticIdentity.loop" as Bend.Name;
  const recursiveCall = Bend.App(Bend.Ref(loop), Bend.Lit(0));
  const recursiveBody = Bend.term_lower(Bend.Lam(loop, 0,
    (n: HTerm) => Bend.App(Bend.Ref(loop), n)));
  book = static_identity_test_book(generic,
    [[Bend.Ann(recursiveCall, type1), first]]);
  (book.tlds as Record<string, TLD>)[loop] = {
    $: "Def", n: 1, x: 0, e: recursiveBody, v: recursiveBody,
  } as TLD;
  static_identity_test_assert(
    static_template_instance(book, generic, [recursiveCall]) === first,
    "recursive closed syntax is matched structurally without normalization");

  const many: Array<[HTerm, Bend.Name]> = [];
  for (let i = 0; i <= STATIC_TEMPLATE_SCAN_LIMIT; i++) {
    many.push([Bend.Ref(("StaticIdentity.entry" + i) as Bend.Name), first]);
  }
  book = static_identity_test_book(generic, many);
  static_identity_test_assert(
    static_template_instance(book, generic, [base]) === null,
    "oversized template tables refuse specialization");

  let deep: HTerm = Bend.Ref("StaticIdentity.function" as Bend.Name);
  for (let i = 0; i <= STATIC_SPINE_LIMIT; i++) {
    deep = Bend.App(deep, base);
  }
  static_identity_test_assert(static_unapply(deep) === null,
    "oversized application spines refuse specialization");

  const factory = "StaticIdentity.factory" as Bend.Name;
  const value1 = "StaticIdentity.value1" as Bend.Name;
  const value2 = "StaticIdentity.value2" as Bend.Name;
  const body1 = Bend.term_lower(static_identity_test_body(value1));
  const body2 = Bend.term_lower(static_identity_test_body(value2));
  const makeBook = (body: LTerm): Book => ({
    tlds: { [factory]: { $: "Def", n: 0, x: 0, e: body, v: body } },
    tmps: Object.create(null),
  } as unknown as Book);
  const book1 = makeBook(body1);
  const book2 = makeBook(body2);
  const ref = Bend.Ref(factory);
  const get_value = (term: HTerm | null): Bend.Name | null => {
    const fn = term === null ? null : Bend.term_strip(term);
    if (fn?.$ !== "Lam") return null;
    const result = Bend.term_strip(fn.f(Bend.Ref("StaticIdentity.unit" as Bend.Name)));
    return result.$ === "Ref" ? result.k : null;
  };
  static_identity_test_assert(get_value(static_fun(book1, ref)) === value1,
    "first Book resolves its own cached static body");
  static_identity_test_assert(get_value(static_fun(book2, ref)) === value2,
    "a second Book cannot reuse the first Book's cache entry");
  static_identity_test_assert(get_value(static_fun(book1, ref)) === value1,
    "repeated lookups remain stable within one Book");
}
static_identity_self_test();
