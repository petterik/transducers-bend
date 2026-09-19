"""Program-specific loop-versioning diagnostic; NOT automatic compiler recognition.

All names/positions below are assertions about the range benchmark only. The fast
scalar body comes from the existing automatic compiler; the guard and call-chain
cloning are manually selected to measure the proposed next compiler strategy.
"""
import re

def version_range(original, automatic, bailout=False, min_two=False):
    def function(code, name):
        m=re.search(r'INLINE Term '+re.escape(name)+r'\([^\n]*\) \{.*?\n\}',code,re.S)
        assert m,name
        return m[0]
    scalar=function(original,'spin_4')
    assert 'u32 keep_0 = r0;' in scalar and 'Term inner_0 = r2;' in scalar
    fast=function(automatic,'spin_4')
    assert '_guarded_fallback' in fast
    fast,n=re.subn(r'  if \(!\(.*?\n  \}\n','',fast,count=1,flags=re.S)
    assert n==1 and '_guarded_fallback' not in fast
    fast=fast.replace('spin_4(','spin_4_version_fast(',1)
    feed=function(original,'spin_8')
    assert 'spin_4(e, o_4, v_22, state_0, state_1, state_2, state_3, x_1)' in feed
    fastfeed=feed.replace('spin_8(','spin_8_version_fast(',1).replace('spin_4(','spin_4_version_fast(')
    driver=function(original,'spin_10')
    assert 'Term c_7 = r3;' in driver and 'u32 c_8 = r4;' in driver and 'WL_AGAIN(spin_10)' in driver
    assert 'spin_8(e, o_2, c_6, c_7, c_8, c_9, v_12)' in driver
    generic=driver.replace('spin_10','spin_10_version_generic')
    fastdriver=driver.replace('spin_10','spin_10_version_fast').replace('spin_8(','spin_8_version_fast(')
    if bailout:
        # Check at the step boundary; once a guard fails the original driver
        # completes the remaining source. No inductive assumption is required.
        anchor = '        u32 v_10 = 0;'
        assert fastdriver.count(anchor)==1
        transfer = '''        if (c_7 == 0 || c_8 != 0) {
          return spin_10_version_generic(e, o, remaining_0, c_5, c_6, c_7, c_8, c_9, end_1);
        }
'''
        fastdriver=fastdriver.replace(anchor,transfer+anchor)
    header=driver.split('{',1)[0]
    wrapper=header+'''{
  // Experiment-only entry check. Positive count / continuing inner is inductive
  // while the outer result continues. Generic zero/stopped states are preserved.
  if (r3 != 0 && r4 == 0) return spin_10_version_fast(e, o, r0, r1, r2, r3, r4, r5, r6);
  return spin_10_version_generic(e, o, r0, r1, r2, r3, r4, r5, r6);
}'''
    if min_two:
        assert not bailout
        # Diagnostic profitability restriction: both source and accepted-input
        # budgets permit at least two iterations. This is not an inferred fact.
        wrapper=wrapper.replace('r3 != 0 && r4 == 0', 'r0 > 1 && r3 > 1 && r4 == 0')
    if bailout:
        wrapper=header+'{\n  return spin_10_version_fast(e, o, r0, r1, r2, r3, r4, r5, r6);\n}'
    code=original.replace(scalar,scalar+'\n'+fast).replace(feed,feed+'\n'+fastfeed).replace(driver,generic+'\n'+fastdriver+'\n'+wrapper)
    return code
