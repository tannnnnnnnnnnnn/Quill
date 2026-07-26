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
    const callPath =
      /\/(?:v2|meet|l\/meetup-join|_#\/conversations)(?:\/|$)/i.test(path) ||
      url.hash.includes("meeting");
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

export function hasActiveMeetingMedia(root = document) {
  const media = [...root.querySelectorAll("audio, video")];
  const active = media.filter((element) => {
    const stream = element.srcObject;
    const hasLiveTrack =
      stream &&
      typeof stream.getTracks === "function" &&
      stream.getTracks().some((track) => track.readyState === "live");
    return (
      hasLiveTrack ||
      (element.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
        !element.paused &&
        !element.ended)
    );
  });

  const videos = media.filter((element) => element.tagName === "VIDEO");
  return active.length > 0 && (media.length > 1 || videos.length > 1);
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
   * Zoom, Teams, and Webex in-call chrome has not been measured. Preserve their
   * existing URL-plus-media behavior instead of guessing platform selectors.
   */
  return {
    active: platform.urlStrongSignal && hasActiveMeetingMedia(root),
    platform
  };
}
