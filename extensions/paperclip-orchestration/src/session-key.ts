export type PaperclipSessionInfo =
  | { type: "issue"; issueId: string }
  | { type: "run"; runId: string };

/**
 * Paperclip sets session keys in the format:
 *   paperclip:issue:{issueId}   (default strategy)
 *   paperclip:run:{runId}       (run strategy)
 *
 * Returns null for non-Paperclip sessions.
 */
export function parsePaperclipSessionKey(sessionKey: string): PaperclipSessionInfo | null {
  if (!sessionKey.startsWith("paperclip:")) return null;

  const parts = sessionKey.split(":");
  if (parts.length < 3) return null;

  if (parts[1] === "issue" && parts[2]) {
    return { type: "issue", issueId: parts[2] };
  }
  if (parts[1] === "run" && parts[2]) {
    return { type: "run", runId: parts[2] };
  }

  return null;
}

export function isPaperclipSession(sessionKey: string | undefined): boolean {
  return !!sessionKey && sessionKey.startsWith("paperclip:");
}
