"""Program-specific generated-C policy diagnostics, never compiler recognition."""
import re

def policies(original, automatic):
    def body(code,name):
        m=re.search(r'INLINE Term '+re.escape(name)+r'\([^\n]*\) \{.*?\n\}',code,re.S)
        assert m,name
        return m[0]
    root='spin_10';generic=root+'_loop_generic'
    wrapper=body(automatic,root);old=body(original,root)
    assert 'Term remaining_0 = r0;' in old and 'u32 c_5 = r1;' in old
    assert 'Term c_7 = r3;' in old and 'u32 c_8 = r4;' in old
    fast=re.search(r'if \(.*?\) return (spin_\d+)\(e, o,',wrapper)[1]
    args='e, o, r0, r1, r2, r3, r4, r5, r6'
    gate=wrapper.replace(' {\n',' {\n  if (r0 <= 1) return '+generic+'('+args+');\n',1)
    # Explicit polling state is carried across the one-time handoff. The
    # dispatcher's terminal return performs the next original loop poll too.
    def resume(code,name):
        return code.replace(name+'(',name+'_resume(',1).replace('u32 r6) {','u32 r6, u32 entered) {',1).replace('u32 wpoll = 0;','u32 wpoll = entered;',1)
    dispatch=wrapper.replace(root+'(',root+'_dispatch(',1).replace('u32 r6) {','u32 r6, u32 entered) {',1)
    terminal='''  if (r0 == 0 || r1 == 1) {
    if (err_spun(e.mem, &entered)) return 0;
    o[0]=r1; o[1]=r2; o[2]=r3; o[3]=r4; o[4]=r5;
    return 1;
  }
'''
    dispatch=dispatch.replace(' {\n',' {\n'+terminal,1)
    for name in [fast,generic]:dispatch=dispatch.replace(name+'('+args+')',name+'_resume('+args+', entered)')
    peeled=old.replace('WL_AGAIN('+root+');','return '+root+'_dispatch('+args+', wpoll);')
    assert peeled!=old and '_resume(' in dispatch
    replacements='\n'.join([resume(body(automatic,generic),generic),resume(body(automatic,fast),fast),dispatch,peeled])
    feed=body(original,'spin_8')
    assert 'v_22 = v_23;' in feed and 'spin_4(e, o_4, v_22,' in feed
    trigger=feed.replace('spin_8(', 'spin_8_trigger(',1).replace('  u32 wpoll = 0;', '  u32 wpoll = 0;\n  Term selected = 0;',1)
    trigger=trigger.replace('    v_22 = v_23;', '    v_22 = v_23;\n    selected = v_22;',1).replace('  return 1;','  o[5] = selected;\n  return 1;',1)
    lazy=old.replace('Term o_2[5];','Term o_2[6];',1).replace('spin_8(e, o_2,','spin_8_trigger(e, o_2,',1)
    # Keep the original driver until a predicate accepts. Test the proven fast
    # guard only then; carry polling state on the one-time handoff. No assumed
    # tag/count fact from the predicate is needed for correctness.
    lazy=lazy.replace('WL_AGAIN('+root+');', 'if (o_2[5] && r0 != 0 && r3 != 0 && r4 == 0) return '+fast+'_resume('+args+', wpoll);\n        WL_AGAIN('+root+');')
    lazy_parts='\n'.join([trigger,resume(body(automatic,fast),fast),lazy])
    lazy_gate=lazy.replace(' {\n',' {\n  if (r0 <= 1) return '+generic+'('+args+');\n',1)
    lazy_gate_parts='\n'.join([trigger,resume(body(automatic,fast),fast),lazy_gate])
    constant,n=re.subn(r'  if \((.*)\) return '+fast,lambda m:'  if (__builtin_constant_p(('+m[1]+')) && ('+m[1]+')) return '+fast,wrapper,count=1)
    assert n==1
    region_guard=re.search(r'  if \((.*)\) return '+fast,wrapper)[1]+' && r0 > 1'
    region=wrapper.replace(re.search(r'  if \((.*)\) return '+fast,wrapper)[0], '  if (__builtin_constant_p(('+region_guard+')) && ('+region_guard+')) return '+fast,1)
    region=region.replace('INLINE Term', 'INLINE __attribute__((always_inline)) Term',1)
    constant_inline=constant.replace('INLINE Term', 'INLINE __attribute__((always_inline)) Term',1)
    macro_guard=re.sub(r'\br(\d+)\b',lambda m:'(A'+m[1]+')',region_guard)
    macro_args=', '.join(['(E)','(O)']+['(A'+str(i)+')' for i in range(7)])
    macro='#define '+root+'(E,O,A0,A1,A2,A3,A4,A5,A6) (__builtin_constant_p(('+macro_guard+')) && ('+macro_guard+') ? '+fast+'('+macro_args+') : ('+root+')('+macro_args+'))'
    callsite=old+'\n'+macro
    return {'original':original,'entry':automatic,'source_gate':automatic.replace(wrapper,gate),
            'peel':automatic.replace(wrapper,replacements),'lazy':automatic.replace(wrapper,lazy_parts),'lazy_gate':automatic.replace(wrapper,lazy_gate_parts),'constant_guard':automatic.replace(wrapper,constant),'constant_inline':automatic.replace(wrapper,constant_inline),'constant_region':automatic.replace(wrapper,region),'callsite_const':automatic.replace(wrapper,callsite)}
