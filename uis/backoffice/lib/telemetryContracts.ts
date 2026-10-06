import registry from "../../../docs/telemetry/event-schemas.json";

export const TELEMETRY_SCHEMA_VERSION = registry.formatVersion;
export const TELEMETRY_MAX_EVENT_BYTES = registry.validationRules.maxEventBytes;

interface PropertyRule {
  type: string;
  enum?: readonly unknown[];
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  format?: string;
}
interface Contract {
  event_type: string;
  schemaVersion: string;
  requiredProperties: string[];
  properties: Record<string, PropertyRule | undefined>;
}
const contracts = new Map<string, Contract>(
  registry.events.map((contract) => [contract.event_type, contract]),
);

export function validTelemetryProperties(eventType: string, properties: Record<string, unknown>): boolean {
  const contract = contracts.get(eventType);
  if (!contract || contract.schemaVersion !== TELEMETRY_SCHEMA_VERSION
    || !properties || Array.isArray(properties)
    || contract.requiredProperties.some((name) => !Object.hasOwn(properties, name))) return false;
  return Object.entries(properties).every(([name, value]) => {
    const rule = contract.properties[name];
    if (!rule) return false;
    if (rule.type === "integer" ? !Number.isInteger(value) : typeof value !== rule.type) return false;
    if (typeof value === "number" && (!Number.isFinite(value)
      || value < (rule.minimum ?? -Infinity) || value > (rule.maximum ?? Infinity))) return false;
    if (typeof value === "string" && (value.length < (rule.minLength ?? 0)
      || value.length > (rule.maxLength ?? TELEMETRY_MAX_EVENT_BYTES)
      || (rule.pattern && !new RegExp(rule.pattern).test(value)))) return false;
    if (rule.enum && !rule.enum.includes(value)) return false;
    if (rule.format === "date") {
      if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
      const parsed = new Date(value);
      if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return false;
    }
    return true;
  });
}