import {
  CandidateCreatePayload,
  CandidatePatchPayload,
  CandidateRecord,
  NotesResponse,
  NoteCreatePayload,
  RecordsResponse,
} from "@/types/candidate";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  throw new Error("Falta NEXT_PUBLIC_API_URL en las variables de entorno.");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const fallback = `Error ${response.status}: ${response.statusText}`;

    try {
      const errorJson = (await response.json()) as { detail?: unknown };
      const detail = Array.isArray(errorJson.detail)
        ? JSON.stringify(errorJson.detail)
        : typeof errorJson.detail === "string"
          ? errorJson.detail
          : fallback;
      throw new Error(detail);
    } catch {
      throw new Error(fallback);
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export interface RecordsQueryParams {
  status?: string;
  stage?: string;
  search?: string;
  page?: number;
  limit?: number;
}

export async function getRecords(params: RecordsQueryParams): Promise<RecordsResponse> {
  const query = new URLSearchParams();

  if (params.status) query.set("status", params.status);
  if (params.stage) query.set("stage", params.stage);
  if (params.search) query.set("search", params.search);
  if (params.page) query.set("page", String(params.page));
  if (params.limit) query.set("limit", String(params.limit));

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<RecordsResponse>(`/records${suffix}`);
}

export async function getRecordById(id: string): Promise<CandidateRecord> {
  return request<CandidateRecord>(`/records/${id}`);
}

export async function createRecord(payload: CandidateCreatePayload): Promise<CandidateRecord> {
  return request<CandidateRecord>("/records", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function replaceRecord(id: string, payload: CandidateCreatePayload): Promise<CandidateRecord> {
  return request<CandidateRecord>(`/records/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function patchRecord(id: string, payload: CandidatePatchPayload): Promise<CandidateRecord> {
  return request<CandidateRecord>(`/records/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getNotes(recordId: string): Promise<NotesResponse> {
  return request<NotesResponse>(`/records/${recordId}/notes`);
}

export async function addNote(recordId: string, payload: NoteCreatePayload): Promise<void> {
  await request<void>(`/records/${recordId}/notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteNote(recordId: string, noteId: string): Promise<void> {
  await request<void>(`/records/${recordId}/notes/${noteId}`, {
    method: "DELETE",
  });
}
