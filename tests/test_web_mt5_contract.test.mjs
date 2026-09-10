import test from "node:test";
import assert from "node:assert/strict";

const source = await (await fetch("https://raw.githubusercontent.com/nongamertvchop-hue/Ariatrading/fix/mt5-single-source-web-runtime/Webaria/live-market.js")).text();

test("browser live market bridge uses MT5 market and signal endpoints only", () => {
  assert.match(source, /\/api\/market\?/);
  assert.match(source, /\/api\/signal\?/);
  assert.doesNotMatch(source, /\/api\/strategy/);
  assert.match(source, /source:'mt5'/);
});
