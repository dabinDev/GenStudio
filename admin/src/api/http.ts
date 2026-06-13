const GENERIC_ERROR_MESSAGE = '请求失败，请稍后重试。';

let adminCsrfToken = '';

export class AdminApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown = null) {
    super(message);
    this.name = 'AdminApiError';
    this.status = status;
    this.payload = payload;
  }
}

export function extractApiMessage(payload: unknown): string {
  if (!payload || typeof payload !== 'object') {
    return GENERIC_ERROR_MESSAGE;
  }

  const data = payload as { detail?: unknown; message?: unknown };
  if (data.detail && typeof data.detail === 'object') {
    const detail = data.detail as { message?: unknown };
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message.trim();
    }
  }

  if (typeof data.message === 'string' && data.message.trim()) {
    return data.message.trim();
  }

  return GENERIC_ERROR_MESSAGE;
}

export function setAdminCsrfToken(token: string): void {
  adminCsrfToken = token;
}

function isJsonResponse(response: Response): boolean {
  return response.headers.get('content-type')?.includes('application/json') ?? false;
}

export async function adminRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);

  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && adminCsrfToken) {
    headers.set('X-CSRF-Token', adminCsrfToken);
  }

  const response = await fetch(path, {
    ...init,
    method,
    credentials: 'include',
    headers,
  });

  const payload = isJsonResponse(response)
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '');

  if (!response.ok) {
    throw new AdminApiError(extractApiMessage(payload), response.status, payload);
  }

  return payload as T;
}
