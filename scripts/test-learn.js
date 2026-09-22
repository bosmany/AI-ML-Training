// Unit tests for the scheduling / mastery / streak math in assets/learn.js
// Run: node scripts/test-learn.js
const assert = require('assert');
const L = require('../assets/learn.js');
const H = L._;
const T = (d, h = 12) => new Date(d + 'T' + String(h).padStart(2, '0') + ':00:00').getTime();
const near = (a, b, e = 1e-6) => assert(Math.abs(a - b) <= e, a + ' !~ ' + b);

// --- SM-2-lite ---
let it = { skill: 's.a', kind: 'quiz', ease: 2.5, interval: 1, reps: 0, lapses: 0 };
let a = H.schedule(it, true, '2026-03-01', 1);
assert.deepStrictEqual([a.interval, a.reps, a.ease, a.due, a.last], [1, 1, 2.55, '2026-03-02', 1]);
a = H.schedule(a, true, '2026-03-02', 2);
assert.deepStrictEqual([a.interval, a.reps, a.ease, a.due], [3, 2, 2.6, '2026-03-05']);
a = H.schedule(a, true, '2026-03-05', 3);
assert.deepStrictEqual([a.interval, a.reps, a.ease, a.due], [8, 3, 2.65, '2026-03-13']); // round(3*2.6)
a = H.schedule(a, true, '2026-03-13', 4);
assert.strictEqual(a.interval, 21); // round(8*2.65)
let f = H.schedule(a, false, '2026-04-03', 5);
assert.deepStrictEqual([f.interval, f.reps, f.lapses, f.last, f.due], [1, 0, 1, 0, '2026-04-04']);
near(f.ease, 2.5); // 2.7 - 0.2 (ease after 4 successes = 2.7)
let e = { ease: 1.35, interval: 1, reps: 0, lapses: 0 };
assert.strictEqual(H.schedule(e, false, '2026-01-01', 0).ease, 1.3); // floor
e = { ease: 2.98, interval: 5, reps: 5, lapses: 0 };
assert.strictEqual(H.schedule(e, true, '2026-01-01', 0).ease, 3); // ceiling

// --- retention ---
near(H.retention({ ts: 0, interval: 2 }, 3 * 864e5), Math.exp(-1)); // 3d / (2*1.5)
near(H.retention({ ts: 5, interval: 1 }, 5), 1);

// --- dates / streak ---
assert.strictEqual(H.addDays('2026-02-27', 2), '2026-03-01');
assert.strictEqual(H.diffDays('2026-12-31', '2027-01-02'), 2);
assert.strictEqual(H.weekKey('2026-03-01'), '2026-02-23'); // Sunday -> its Monday
let st = { count: 0, best: 0, lastDay: '', freezes: 1 };
st = H.streakAdvance(st, '2026-03-02'); assert.strictEqual(st.count, 1);
st = H.streakAdvance(st, '2026-03-02'); assert.strictEqual(st.count, 1); // same day
st = H.streakAdvance(st, '2026-03-03'); assert.strictEqual(st.count, 2);
st = H.streakAdvance(st, '2026-03-05'); // missed Wed, freeze covers it
assert.deepStrictEqual([st.count, st.freezes, st.best], [3, 0, 3]);
st = H.streakAdvance(st, '2026-03-07'); // missed Fri, no freeze left, same week -> reset
assert.deepStrictEqual([st.count, st.best], [1, 3]);
st = { count: 5, best: 9, lastDay: '2026-03-06', freezes: 0 };
st = H.streakAdvance(st, '2026-03-09'); // new ISO week (Mon): freeze refilled, missed Sat+Sun = 2 > 1 -> reset
assert.strictEqual(st.count, 1);
st = { count: 5, best: 9, lastDay: '2026-03-08', freezes: 0 };
st = H.streakAdvance(st, '2026-03-10'); // missed Monday only, freeze refilled in new week
assert.deepStrictEqual([st.count, st.freezes], [6, 0]);

// --- recordResult end to end (in-memory store) ---
L.reset();
const d1 = T('2026-03-01');
let r = L.recordResult('ch04:q1', true, { skill: 'python.ch04', now: d1 });
assert.strictEqual(r.dup, false);
let s = L.getState();
assert.strictEqual(s.items['ch04:q1'].due, '2026-03-02');
assert.strictEqual(s.activity['2026-03-01'].n, 1);
assert.strictEqual(s.streak.count, 1);
near(s.skills['python.ch04'].acc, 0.3);
// mastery = 100*(0.5*acc + 0.3*ret + 0.2*breadth) = 100*(0.15 + 0.3*1 + 0.2*0.1) = 47
near(L.mastery('python.ch04', { now: d1 }), 47, 1e-9);
// same-day repeat of same result is a duplicate: no scheduling / acc / activity change
assert.strictEqual(L.recordResult('ch04:q1', true, { skill: 'python.ch04', now: d1 + 1000 }).dup, true);
assert.strictEqual(L.getState().activity['2026-03-01'].n, 1);
// wrong answer on another item
L.recordResult('ch04:q2', false, { skill: 'python.ch04', now: d1 + 2000 });
s = L.getState();
near(s.skills['python.ch04'].acc, 0.21); // 0.7*0.3
assert.strictEqual(s.items['ch04:q2'].lapses, 1);
// mastery: acc .21, ret 1, breadth 1/10 -> 100*(.105+.3+.02)=42.5
near(L.mastery('python.ch04', { now: d1 + 2000 }), 42.5, 1e-9);
// retention decay: 3 days later, both items interval 1 -> R = exp(-3/1.5)
const later = d1 + 3 * 864e5;
near(L.mastery('python.ch04', { now: later }), 100 * (0.5 * 0.21 + 0.3 * Math.exp(-2) + 0.02), 0.06);
// due queue: q1 due 03-02; q2 missed (relearn) -> both appear on 03-02, only q2 on 03-01
assert.deepStrictEqual(L.dueItems({ now: d1 + 5000 }).map(x => x.id), ['ch04:q2']);
assert.deepStrictEqual(L.dueItems({ now: T('2026-03-02') }).map(x => x.id).sort(), ['ch04:q1', 'ch04:q2']);
assert.strictEqual(L.dueItems({ now: d1 + 5000, relearn: false }).length, 0);
assert.strictEqual(L.nextDue({ now: d1 }), '2026-03-02');
// domain mastery falls back to state ids when no skills.json loaded: single skill in domain
near(L.domainMastery('python', { now: d1 + 2000 }), 42.5, 1e-9);
// export / import round trip
const dump = L.exportJSON(); L.reset();
assert.strictEqual(Object.keys(L.getState().items).length, 0);
assert.deepStrictEqual(L.importJSON(dump), { items: 2, skills: 1 });
assert.strictEqual(L.getState().items['ch04:q2'].lapses, 1);
assert.throws(() => L.importJSON('{"x":1}'));
assert.throws(() => L.importJSON('nope'));
// other features' keys survive read-modify-write
let raw = L.getState(); raw.placement = { ts: 1, vector: { python: 50 }, path: 'mid' };
L.importJSON({ format: 'aimlZTH_learn_export', learn: raw });
L.recordResult('ch04:q3', true, { skill: 'python.ch04', now: T('2026-03-02') });
assert.strictEqual(L.getState().placement.path, 'mid');
// streakInfo
assert.strictEqual(L.streak({ now: T('2026-03-02', 20) }).count, 2);
assert.strictEqual(L.streak({ now: T('2026-03-04') }).count, 2);   // 1 missed day covered by the freeze
assert.strictEqual(L.streak({ now: T('2026-03-04') }).atRisk, true);
assert.strictEqual(L.streak({ now: T('2026-03-06') }).count, 0);   // broken
console.log('learn.js math: all assertions passed');
