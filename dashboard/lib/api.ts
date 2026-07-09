const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const api = {
  get<T>(path: string): Promise<T | null> {
    return request<T>("GET", path);
  },
  post<T>(path: string, body: unknown): Promise<T | null> {
    return request<T>("POST", path, body);
  },
  del<T>(path: string): Promise<T | null> {
    return request<T>("DELETE", path);
  },
};
