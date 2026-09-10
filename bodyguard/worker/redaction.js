/**
 * Bodyguard(Aria) data-loss prevention primitives.
 *
 * Boundary rule: attacker-controlled values may be logged only after they pass
 * through this sanitizer. Secrets are also rejected by key name, not only by
 * value shape, because a real credential may not match a known token format.
 */

export const REDACTED = "[REDACTED]";

const SENSITIVE_KEY_RE = /(?:^|[_-])(api[_-]?key|access[_-]?token|auth(?:orization)?|bearer|password|passwd|secret|private[_-]?key|client[_-]?secret|refresh[_-]?token|session[_-]?token|cookie|set[_-]?cookie)(?:$|[_-])/i;
const SECRET_VALUE_RES = [
  /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----/g,
  /\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/gi,
  /\b(?:sk|pk)_[A-Za-z0-9_-]{16,}\b/g,
  /\bAIza[0-9A-Za-z_-]{20,}\b/g,
  /\bgh[pousr]_[A-Za-z0-9_]{20,}\b/g,
  /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g,
];

function redactString(value) {
  let result = String(value);
  for (const pattern of SECRET_VALUE_RES) result = result.replace(pattern, REDACTED);
  return result;
}

export function sanitizeForBoundary(value, { maxDepth = 8, maxItems = 200 } = {}) {
  const visit = (item, depth) => {
    if (depth > maxDepth) return REDACTED;
    if (item === null || typeof item === "boolean" || typeof item === "number") return item;
    if (typeof item === "string") return redactString(item);

    if (Array.isArray(item)) {
      return item.slice(0, maxItems).map((child) => visit(child, depth + 1));
    }

    if (typeof item === "object") {
      const result = Object.create(null);
      let index = 0;
      for (const [key, child] of Object.entries(item)) {
        if (index >= maxItems) {
          result["[TRUNCATED]"] = REDACTED;
          break;
        }
        result[String(key)] = SENSITIVE_KEY_RE.test(String(key))
          ? REDACTED
          : visit(child, depth + 1);
        index += 1;
      }
      return result;
    }

    return redactString(item);
  };

  return visit(value, 0);
}
