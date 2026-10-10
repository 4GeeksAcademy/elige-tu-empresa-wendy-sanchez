interface EnvelopeContext { requestId?: string; eventId?: string; timestamp?: string }
let context: EnvelopeContext | undefined;

export function telemetryEnvelopeContext(): EnvelopeContext | undefined { return context; }
export function withTelemetryEnvelope<T>(value: EnvelopeContext, operation: () => T): T {
  const previous = context;
  context = value;
  try { return operation(); } finally { context = previous; }
}