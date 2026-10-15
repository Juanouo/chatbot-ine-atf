(function () {
  window.DockerBehaviorRules = window.DockerBehaviorRules || {};
  const cfg = window.DockerBehaviorRules.config || {};
  const rules = Array.isArray(cfg.rules) ? cfg.rules : [];

  function currentPath() {
    return window.location && window.location.pathname ? window.location.pathname : "/";
  }

  function scopeMatches(scope) {
    if (!scope || scope.type === "all") return true;

    const path = currentPath();
    const href = window.location && window.location.href ? window.location.href : "";

    if (scope.type === "url_path_exact") return path === scope.value;
    if (scope.type === "url_path_prefix") return path.startsWith(scope.value);
    if (scope.type === "url_contains") return href.includes(scope.value);

    return true;
  }

  function isSecureContext() {
    return window.location && window.location.protocol === "https:";
  }

  function setCookie({ name, value, days, path, domain, sameSite }) {
    if (!name) return;

    const parts = [];
    parts.push(`${encodeURIComponent(name)}=${encodeURIComponent(value ?? "")}`);

    if (typeof days === "number") {
      const date = new Date();
      date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
      parts.push(`Expires=${date.toUTCString()}`);
    }

    parts.push(`Path=${path || "/"}`);
    if (domain) parts.push(`Domain=${domain}`);

    const ss = sameSite || "Lax";
    parts.push(`SameSite=${ss}`);

    if (ss === "None" || isSecureContext()) parts.push("Secure");

    document.cookie = parts.join("; ");
  }

  function destroyCookie(name, options = {}) {
    setCookie({
      name,
      value: "",
      days: -1,
      path: options.path || "/",
      domain: options.domain || "",
      sameSite: options.sameSite || "Lax",
    });
  }

  // Public cookie API
  window.DockerBehaviorRules.cookies = {
    set: setCookie,
    destroy: destroyCookie,
  };

  // Action registry
  const actions = {
    set_cookie: ({ rule }) => {
      setCookie(rule.cookie || {});
    },
  };

  // Event attachers
  const attachers = {
    click: (handler) => document.addEventListener("click", handler, true),

    page_view: (handler) => {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => handler({ type: "page_view", target: document }), { once: true });
      } else {
        handler({ type: "page_view", target: document });
      }
    },
  };

  // Group by event
  const byEvent = new Map();
  for (const rule of rules) {
    if (!rule || rule.enabled === false) continue;
    const ev = rule.event || "click";
    if (!byEvent.has(ev)) byEvent.set(ev, []);
    byEvent.get(ev).push(rule);
  }

  for (const [eventType, eventRules] of byEvent.entries()) {
    const attach = attachers[eventType];
    if (!attach) continue;

    attach((e) => {
      for (const rule of eventRules) {
        try {
          if (!scopeMatches(rule.scope)) continue;

          let match = null;
          if (eventType === "click") {
            match = e.target?.closest?.(rule.selector) || null;
            if (!match) continue;
          }

          const action = actions[rule.action];
          if (typeof action === "function") action({ rule, event: e, element: match });
        } catch (err) {
          // ignore invalid selectors/errors
        }
      }
    });
  }
})();