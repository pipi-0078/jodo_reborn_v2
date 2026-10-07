import assert from 'node:assert/strict';
import { FrameScheduler } from '../src/experience/frameScheduler.ts';

for (const hz of [30, 60, 120, 144]) {
  const frames = new FrameScheduler();
  let rendered = 0;
  let animationTime = 0;
  for (let i = 0; i < hz * 10; i++) {
    const dt = frames.step(1 / hz, false, false);
    if (dt !== null) { rendered++; animationTime += dt; }
  }
  assert(rendered <= 100, `${hz}Hz standby stays at or below 10fps`);
  assert(Math.abs(animationTime - 10) < 0.11, `${hz}Hz preserves animation elapsed time`);
  for (let i = 0; i < hz; i++) {
    assert(frames.step(1 / hz, true, false) !== null, 'Inside uses every display frame');
  }
}

const frames = new FrameScheduler();
assert.equal(frames.step(0.02, false, false), null);
assert.equal(frames.step(0.02, true, false), 0.04, 'Entering paints immediately');
assert.equal(frames.step(0.02, false, false), 0.02, 'Exiting paints immediately');
assert.equal(frames.step(0.05, false, false), null);
assert.equal(frames.step(30, false, true), null, 'Hidden tab does no work');
assert.equal(frames.step(0.016, true, false), 0.016, 'Resume has no accumulated hidden time');
assert.equal(frames.step(10, true, false), 0.05, 'Keep the original active-frame stall limit');
console.log('Frame scheduler: standby rate, elapsed time, entry/exit, active refresh and visibility pass.');
