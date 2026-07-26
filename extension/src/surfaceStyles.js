export const SURFACE_STYLES = `
  :host {
    all: initial;
    --quill-ink: #1c1c1c;
    --quill-paper: #f4f2ed;
    --quill-secondary: #6b6b66;
    --quill-tertiary: #9a978f;
    --quill-accent: #4b7bec;
    --quill-accent-hover: #3d6bd8;
    --quill-me: #7db8ff;
    --quill-them: #ffc46b;
    --quill-ghost: rgba(28, 28, 28, 0.05);
    --quill-hairline: rgba(28, 28, 28, 0.07);
    position: fixed;
    inset: 20px 20px auto auto;
    z-index: 2147483647;
    color-scheme: light;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
    color: var(--quill-ink);
    line-height: normal;
    text-align: left;
  }

  *, *::before, *::after {
    box-sizing: border-box;
  }

  button {
    font: inherit;
  }

  .surface {
    background: var(--quill-paper);
    border: 1px solid var(--quill-hairline);
    border-radius: 16px;
    box-shadow: 0 12px 32px rgba(28, 28, 28, 0.12);
    overflow: hidden;
    transform-origin: right top;
    animation: quill-enter 0.55s cubic-bezier(0.2, 0.9, 0.25, 1) both;
  }

  .detected-card {
    width: 360px;
    min-height: 112px;
    padding: 17px;
  }

  .detected-top {
    display: flex;
    align-items: center;
    gap: 13px;
  }

  .icon-slot {
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    display: grid;
    place-items: center;
    border-radius: 12px;
    background: var(--quill-ghost);
  }

  .icon-slot img {
    display: block;
    width: 29px;
    height: 26px;
    object-fit: contain;
  }

  .detected-copy {
    min-width: 0;
  }

  .detected-title {
    margin: 0;
    color: var(--quill-ink);
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.01em;
  }

  .detected-subtitle {
    margin: 2px 0 0;
    overflow: hidden;
    color: var(--quill-secondary);
    font-size: 12.5px;
    font-weight: 400;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .detected-actions {
    display: flex;
    gap: 9px;
    margin-top: 16px;
  }

  .action-button {
    height: 34px;
    border: 0;
    border-radius: 9px;
    cursor: pointer;
    transition: background-color 140ms ease, color 140ms ease, opacity 140ms ease;
  }

  .action-button:focus-visible,
  .close-button:focus-visible {
    outline: 2px solid var(--quill-accent);
    outline-offset: 2px;
  }

  .action-button:disabled {
    cursor: default;
    opacity: 0.62;
  }

  .ghost-button {
    flex: 0 0 auto;
    padding: 0 16px;
    background: var(--quill-ghost);
    color: var(--quill-ink);
    font-size: 13px;
    font-weight: 500;
  }

  .ghost-button:hover:not(:disabled) {
    background: rgba(28, 28, 28, 0.09);
  }

  .primary-button {
    flex: 1 1 auto;
    padding: 0 16px;
    background: var(--quill-accent);
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
  }

  .primary-button:hover:not(:disabled) {
    background: var(--quill-accent-hover);
  }

  .live-panel {
    width: 340px;
    height: 452px;
    display: flex;
    flex-direction: column;
  }

  .panel-header {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 9px;
    min-height: 51px;
    padding: 14px 15px 12px;
    border-bottom: 1px solid var(--quill-hairline);
  }

  .brand-mark {
    display: block;
    width: 21px;
    height: 19px;
    object-fit: contain;
  }

  .wordmark {
    color: var(--quill-ink);
    font-family: ui-serif, "New York", Georgia, serif;
    font-size: 15px;
    font-weight: 600;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-height: 20px;
    padding: 2px 8px;
    border-radius: 20px;
    background: var(--quill-ghost);
    color: var(--quill-tertiary);
    font-size: 11px;
    white-space: nowrap;
  }

  .status-indicator {
    width: 7px;
    height: 7px;
    flex: 0 0 7px;
  }

  .status-pill[data-status="loading"] .status-indicator {
    width: 10px;
    height: 10px;
    flex-basis: 10px;
    border: 1.5px solid rgba(75, 123, 236, 0.22);
    border-top-color: var(--quill-accent);
    border-radius: 50%;
    animation: quill-spin 0.8s linear infinite;
  }

  .status-pill[data-status="live"] {
    color: var(--quill-secondary);
  }

  .status-pill[data-status="live"] .status-indicator {
    border-radius: 50%;
    background: var(--quill-accent);
    animation: quill-pulse 1.7s ease-in-out infinite;
  }

  .status-pill[data-status="offline"] .status-indicator {
    border-radius: 50%;
    background: var(--quill-them);
  }

  .panel-spacer {
    flex: 1 1 auto;
  }

  .clock {
    color: var(--quill-tertiary);
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .close-button {
    width: 24px;
    height: 24px;
    flex: 0 0 24px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: 7px;
    background: var(--quill-ghost);
    color: var(--quill-secondary);
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    transition: background-color 140ms ease;
  }

  .close-button:hover {
    background: rgba(28, 28, 28, 0.1);
  }

  .transcript-body {
    min-height: 0;
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    gap: 18px;
    overflow-y: auto;
    padding: 18px 16px;
    scrollbar-color: rgba(28, 28, 28, 0.18) transparent;
    scrollbar-width: thin;
  }

  .empty-state {
    flex: 1 1 auto;
    display: grid;
    align-content: center;
    justify-items: center;
    gap: 10px;
    min-height: 120px;
    color: var(--quill-tertiary);
    text-align: center;
  }

  .empty-spinner {
    width: 17px;
    height: 17px;
    border: 1.5px solid rgba(75, 123, 236, 0.2);
    border-top-color: var(--quill-accent);
    border-radius: 50%;
    animation: quill-spin 0.8s linear infinite;
  }

  .empty-title {
    color: var(--quill-tertiary);
    font-size: 12.5px;
  }

  .empty-detail {
    max-width: 230px;
    color: var(--quill-tertiary);
    font-size: 11.5px;
    line-height: 1.45;
  }

  .transcript-line {
    width: fit-content;
    max-width: 90%;
    color: var(--quill-ink);
    animation: quill-line-in 0.4s ease both;
  }

  .transcript-line.them {
    align-self: flex-start;
    text-align: left;
  }

  .transcript-line.me {
    align-self: flex-end;
    text-align: right;
  }

  .speaker-row {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-bottom: 4px;
    color: var(--quill-secondary);
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .me .speaker-row {
    justify-content: flex-end;
  }

  .speaker-dot {
    width: 6px;
    height: 6px;
    flex: 0 0 6px;
    border-radius: 50%;
  }

  .them .speaker-dot {
    background: var(--quill-them);
  }

  .me .speaker-dot {
    background: var(--quill-me);
  }

  .transcript-text {
    margin: 0;
    color: var(--quill-ink);
    font-size: 13.5px;
    line-height: 1.5;
    overflow-wrap: anywhere;
  }

  .panel-footer {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 8px;
    min-height: 37px;
    padding: 11px 15px;
    border-top: 1px solid var(--quill-hairline);
    color: var(--quill-tertiary);
    font-size: 11.5px;
  }

  .waveform {
    height: 14px;
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .waveform span {
    width: 2.5px;
    height: 14px;
    border-radius: 2px;
    background: var(--quill-accent);
    transform: scaleY(0.3);
    animation: quill-wave 1s ease-in-out infinite alternate;
  }

  .waveform span:nth-child(2) { animation-delay: 0.15s; }
  .waveform span:nth-child(3) { animation-delay: 0.3s; }
  .waveform span:nth-child(4) { animation-delay: 0.45s; }

  @keyframes quill-enter {
    from {
      opacity: 0;
      transform: translateX(26px) scale(0.97);
    }
    to {
      opacity: 1;
      transform: translateX(0) scale(1);
    }
  }

  @keyframes quill-spin {
    to { transform: rotate(360deg); }
  }

  @keyframes quill-pulse {
    0%, 100% { opacity: 0.55; transform: scale(0.85); }
    50% { opacity: 1; transform: scale(1); }
  }

  @keyframes quill-wave {
    from { transform: scaleY(0.3); }
    to { transform: scaleY(1); }
  }

  @keyframes quill-line-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @media (max-width: 420px) {
    :host {
      inset: 10px 10px auto auto;
    }

    .detected-card,
    .live-panel {
      width: min(340px, calc(100vw - 20px));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .surface,
    .transcript-line {
      animation-duration: 1ms;
    }

    .status-indicator,
    .empty-spinner,
    .waveform span {
      animation: none !important;
    }
  }
`;
