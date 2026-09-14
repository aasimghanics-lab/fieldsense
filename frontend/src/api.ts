export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Please check your inputs and try again.');
  }
  return response.json();
}
export function queryString(filters: Record<string,string>) {
  return new URLSearchParams(Object.entries(filters).filter(([,v]) => v)).toString();
}
