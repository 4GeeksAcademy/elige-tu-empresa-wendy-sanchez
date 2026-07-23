import { CandidateStage, CandidateStatus } from "@/types/candidate";

export const STATUS_OPTIONS: Array<{ value: CandidateStatus; label: string }> = [
  { value: "received", label: "Recibida" },
  { value: "in_progress", label: "En proceso" },
  { value: "selected", label: "Seleccionada" },
  { value: "discarded", label: "Descartada" },
];

export const STAGE_OPTIONS: Array<{ value: CandidateStage; label: string }> = [
  { value: "pending", label: "Pendiente de revision" },
  { value: "review", label: "En revision" },
  { value: "personal_interview", label: "Entrevista personal" },
  { value: "technical_interview", label: "Entrevista tecnica" },
  { value: "offer_presented", label: "Oferta presentada" },
];

const STATUS_LABELS = Object.fromEntries(STATUS_OPTIONS.map((option) => [option.value, option.label])) as Record<CandidateStatus, string>;
const STAGE_LABELS = Object.fromEntries(STAGE_OPTIONS.map((option) => [option.value, option.label])) as Record<CandidateStage, string>;

export function getStatusLabel(value: CandidateStatus): string {
  return STATUS_LABELS[value] ?? value;
}

export function getStageLabel(value: CandidateStage): string {
  return STAGE_LABELS[value] ?? value;
}
