import assert from 'node:assert/strict';
import test from 'node:test';
import { history, commit, undo, redo } from '../lib/typicals-history.ts';

test('section history restores geometry, mappings and annotation overrides; a new edit clears redo', () => {
  const first = { width: 12, mapping: 'TS_TEST_A', annotations: { title: [0, 0] } };
  const second = { width: 11, mapping: 'TS_TEST_B', annotations: { title: [1, 2] } };
  const state = commit(history(first), second);
  assert.deepEqual(undo(state).present, first);
  assert.deepEqual(redo(undo(state)).present, second);
  assert.equal(commit(undo(state), { ...first, width: 10 }).future.length, 0);
  assert.equal(commit(state, second), state);
  assert.equal(undo(history(first)).present, first);
});
