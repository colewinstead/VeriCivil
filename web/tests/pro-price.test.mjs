import assert from "node:assert/strict";
import test from "node:test";
import { PRO_PRICE, matchesProPrice } from "../lib/billing/pro-price.ts";

const price = { active: true, currency: "usd", unit_amount: 99, type: "recurring", recurring: { interval: "month", interval_count: 1 } };
test("new Pro checkout accepts exactly 99 US cents monthly", () => {
  assert.equal(PRO_PRICE.display, "$0.99/month");
  assert.equal(PRO_PRICE.unitAmount, 99);
  assert.equal(matchesProPrice(price), true);
});
test("checkout blocks outdated prices, different currencies, and different billing periods", () => {
  for (const unit_amount of [2900, 1, 9900, 0, null]) assert.equal(matchesProPrice({ ...price, unit_amount }), false);
  assert.equal(matchesProPrice({ ...price, currency: "eur" }), false);
  assert.equal(matchesProPrice({ ...price, active: false }), false);
  assert.equal(matchesProPrice({ ...price, type: "one_time", recurring: null }), false);
  assert.equal(matchesProPrice({ ...price, recurring: { interval: "year", interval_count: 1 } }), false);
  assert.equal(matchesProPrice({ ...price, recurring: { interval: "month", interval_count: 3 } }), false);
});
