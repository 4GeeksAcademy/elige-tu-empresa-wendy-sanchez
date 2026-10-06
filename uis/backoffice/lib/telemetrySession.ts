interface TelemetrySession {
  sessionId: string;
  userId?: string;
  authenticated: boolean;
}

let session: TelemetrySession | undefined;

export function beginTelemetrySession(userId?: string, newLogin = false): void {
  try {
    const pseudonym = userId && /^[a-f0-9]{64}$/.test(userId) ? userId : undefined;
    if (newLogin || !session?.authenticated || (session.userId && pseudonym && session.userId !== pseudonym)) {
      session = { sessionId: crypto.randomUUID(), userId: pseudonym, authenticated: true };
    } else {
      if (pseudonym) session.userId = pseudonym;
    }
  } catch {
    session = { sessionId: "", authenticated: true };
  }
}

export function clearTelemetrySession(): void {
  session = undefined;
}

export function getTelemetrySession(): { sessionId: string; userId: string } | undefined {
  if (!session) {
    session = {
      sessionId: crypto.randomUUID(), userId: `anonymous_${crypto.randomUUID()}`,
      authenticated: false,
    };
  }
  if (!session.userId || !session.sessionId) return undefined;
  return { sessionId: session.sessionId, userId: session.userId };
}