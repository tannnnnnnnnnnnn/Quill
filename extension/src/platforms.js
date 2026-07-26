const GOOGLE_MEET_CODE = /^\/[a-z]{3}-[a-z]{4}-[a-z]{3}(?:\/|$)/i;
const GOOGLE_MEET_LEAVE_LABEL =
  /^(?:leave (?:the )?(?:call|meeting)|hang up|end call)$/i;

export function platformForUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    return null;
  }

  const host = url.hostname.toLowerCase();
  const path = url.pathname;

  if (host === "meet.google.com") {
    return {
      id: "googleMeet",
      platform: "google-meet",
      label: "Google Meet",
      context: "Google Meet · web",
      urlStrongSignal: GOOGLE_MEET_CODE.test(path)
    };
  }

  if (host.endsWith(".zoom.us") && path.startsWith("/wc/")) {
    return {
      id: "zoom",
      platform: "zoom",
      label: "Zoom",
      context: "Zoom · web",
      urlStrongSignal: true
    };
  }

  if (
    host === "teams.microsoft.com" ||
    host === "teams.cloud.microsoft"
  ) {
    /*
     * The whole Teams web app lives under /v2/, so the path prefix alone means
     * nothing. Key on the markers that only appear for a call: the meetup-join
     * deep link, the pre-join route, and the join query parameter Teams sets
     * when it hands off into a meeting.
     */
    const callPath =
      /\/(?:l\/)?meetup-join(?:\/|$)/i.test(path) ||
      /\/meet(?:\/|$)/i.test(path) ||
      /(?:pre-join-calling|meetup-join|\/meet\/)/i.test(url.hash) ||
      url.searchParams.has("meetingjoin");
    return {
      id: "microsoftTeams",
      platform: "microsoft-teams",
      label: "Microsoft Teams",
      context: "Microsoft Teams · web",
      urlStrongSignal: callPath
    };
  }

  if (host.endsWith(".webex.com")) {
    const callPath =
      /\/(?:meet|join|webappng|m(?:\/|$))/i.test(path) ||
      url.searchParams.has("MTID");
    return {
      id: "webex",
      platform: "webex",
      label: "Webex",
      context: "Webex · web",
      urlStrongSignal: callPath
    };
  }

  return null;
}

export function callKey(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.origin}${parsed.pathname}${parsed.search}`;
  } catch {
    return url;
  }
}

/*
 * Labels for the control that leaves a call, across Zoom, Teams, and Webex.
 * Anchored at both ends so "Leave feedback" does not match; keyboard hints like
 * "Leave (Ctrl+Shift+H)" are stripped before testing. English only for now —
 * a localized UI falls back to no prompt, which is the safe direction.
 */
const LEAVE_CONTROL_LABEL =
  /^(?:leave(?:\s+(?:the\s+)?(?:call|meeting|room))?|hang\s*up|end\s+(?:the\s+)?(?:call|meeting))$/i;

function hasLeaveControl(root) {
  const controls = [...root.querySelectorAll("button, [role='button']")];

  return controls.some((control) =>
    ["aria-label", "data-tooltip", "title"].some((attribute) => {
      const label = control.getAttribute?.(attribute);
      if (!label) return false;
      // drop a trailing keyboard hint: "Leave (Ctrl+Shift+H)" -> "Leave"
      return LEAVE_CONTROL_LABEL.test(label.replace(/\s*\([^)]*\)\s*$/, "").trim());
    })
  );
}

function hasGoogleMeetInCallChrome(root) {
  const controls = [...root.querySelectorAll("button, [role='button']")];

  return controls.some((control) => {
    /*
     * Meet's generated classes and jsname values are undocumented and change
     * between releases. The Material icon ligature is locale-independent, so
     * prefer it over a generated selector. Accessible labels remain a fallback
     * for icon implementations that do not expose the ligature as DOM text.
     * Those labels are localized; the English variants below are deliberately
     * not the only signal, but locales whose UI omits `call_end` may still need
     * an additional measured label in the future.
     */
    const textTokens = String(control.textContent || "")
      .trim()
      .toLowerCase()
      .split(/\s+/);
    if (textTokens.includes("call_end")) return true;

    return ["aria-label", "data-tooltip", "title"].some((attribute) => {
      const label = control.getAttribute?.(attribute);
      return label && GOOGLE_MEET_LEAVE_LABEL.test(label.trim());
    });
  });
}

export function detectInCall(url = location.href, root = document) {
  const platform = platformForUrl(url);
  if (!platform) return { active: false, platform: null };

  if (platform.id === "googleMeet") {
    /*
     * A joined solo Meet with its camera off can have no active media at all,
     * while pre-join can have camera-preview media. The hang-up control is the
     * discriminating signal, and the meeting-code URL excludes /landing.
     */
    return {
      active:
        platform.urlStrongSignal && hasGoogleMeetInCallChrome(root),
      platform
    };
  }

  /*
   * Zoom, Teams, and Webex in-call chrome has not been measured on a real call,
   * so there is no platform-specific selector to key on the way Meet's
   * `call_end` ligature works. Two rejected alternatives:
   *
   *   - Requiring active media. This is the test that missed Meet entirely on a
   *     solo call with the camera off: it under-fires exactly when it matters.
   *   - The URL alone. Every one of these URLs is reached at a pre-join lobby
   *     first, so it would prompt before the user has joined anything, and
   *     again for any tab left open on a meeting page.
   *
   * A leave control is the one thing every call UI has and no lobby does — the
   * same class of signal as Meet's, just matched on the accessible label rather
   * than a measured selector. Being wrong here means no prompt, never a wrong
   * prompt. Replace per platform as each one's chrome gets measured on a call.
   */
  return {
    active: platform.urlStrongSignal && hasLeaveControl(root),
    platform
  };
}
