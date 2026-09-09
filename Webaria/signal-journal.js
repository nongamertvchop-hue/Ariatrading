/*
 * Browser-local signal journal helpers.
 *
 * event_id is the preferred identity. Legacy entries without event_id use a
 * stable fallback so upgrading the UI does not create duplicates immediately.
 */
(function (root) {
  'use strict';

  function legacyKey(entry) {
    return [
      entry.tf ?? '',
      entry.bar_time ?? entry.at ?? '',
      entry.signal ?? '',
      entry.structure ?? '',
      entry.score ?? ''
    ].join('|');
  }

  function entryKey(entry) {
    if (entry && entry.event_id) return 'event:' + entry.event_id;
    return 'legacy:' + legacyKey(entry || {});
  }

  function appendUnique(existing, incoming, maxEntries) {
    const limit = Number.isInteger(maxEntries) && maxEntries > 0 ? maxEntries : 100;
    const result = Array.isArray(existing) ? existing.slice() : [];
    const seen = new Set(result.map(entryKey));

    for (const entry of Array.isArray(incoming) ? incoming : []) {
      const key = entryKey(entry);
      if (seen.has(key)) continue;
      seen.add(key);
      result.push(entry);
    }

    return result.slice(-limit);
  }

  root.WebariaSignalJournal = Object.freeze({ entryKey, legacyKey, appendUnique });
})(typeof window !== 'undefined' ? window : globalThis);
