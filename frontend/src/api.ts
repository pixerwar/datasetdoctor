// FastAPI backend client. In dev, the Vite proxy (vite.config.ts) routes relative
// paths to 127.0.0.1:8000; in prod the same origin is assumed.
import type { ReportResponse, SourceInfo } from './types'

export interface UploadResponse {
  dataset_id: string
  source: SourceInfo
}

export interface AddSourceResponse {
  source: SourceInfo
}

export interface ConfigureResponse {
  job_id: string
  status: string
}

export interface StatusResponse {
  status: 'processing' | 'done' | 'error'
  progress: number
  error?: string
}

// Per-source config keyed by source_id; shape depends on the source mode.
export interface BuildRequest {
  sources: Record<string, Record<string, unknown>>
  embedding_provider?: 'tfidf' | 'semantic'
  model_size?: string
  tag_by_source?: boolean
}

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail ?? detail
    } catch {
      /* body is not JSON */
    }
    throw new Error(detail)
  }
  return resp.json() as Promise<T>
}

/** Upload the first file — creates a dataset and its first source. */
export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch('/datasets/upload', { method: 'POST', body: form })
  return jsonOrThrow<UploadResponse>(resp)
}

/** Add another source (file) to an existing dataset. */
export async function addSource(
  datasetId: string,
  file: File,
): Promise<AddSourceResponse> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`/datasets/${datasetId}/sources`, {
    method: 'POST',
    body: form,
  })
  return jsonOrThrow<AddSourceResponse>(resp)
}

export async function removeSource(
  datasetId: string,
  sourceId: string,
): Promise<void> {
  const resp = await fetch(`/datasets/${datasetId}/sources/${sourceId}`, {
    method: 'DELETE',
  })
  await jsonOrThrow<{ ok: boolean }>(resp)
}

/** Configure all sources and start the build. */
export async function configureDataset(
  datasetId: string,
  body: BuildRequest,
): Promise<ConfigureResponse> {
  const resp = await fetch(`/datasets/${datasetId}/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return jsonOrThrow<ConfigureResponse>(resp)
}

export async function getStatus(datasetId: string): Promise<StatusResponse> {
  const resp = await fetch(`/datasets/${datasetId}/status`)
  return jsonOrThrow<StatusResponse>(resp)
}

export async function getReport(datasetId: string): Promise<ReportResponse> {
  const resp = await fetch(`/datasets/${datasetId}/report`)
  return jsonOrThrow<ReportResponse>(resp)
}

/** Download the ChatML file from the export endpoint. */
export async function downloadExport(
  datasetId: string,
  fileName: string,
): Promise<number> {
  const resp = await fetch(`/datasets/${datasetId}/export`)
  if (!resp.ok) throw new Error('Could not download export')
  const blob = await resp.blob()
  triggerDownload(blob, fileName)
  return blob.size
}

/** Trigger a Blob download in the browser. */
export function triggerDownload(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
