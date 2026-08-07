export type StringProvider = () => Promise<string | undefined> | string | undefined;

export interface TransportOptions {
  fetcher?: typeof fetch;
  getAccessToken?: StringProvider;
  getRequestId?: StringProvider;
}

export async function buildTransportHeaders(
  initialHeaders: HeadersInit | undefined,
  options: TransportOptions,
  accept: string,
): Promise<Headers> {
  const headers = new Headers(initialHeaders);
  headers.set("Accept", accept);

  const accessToken = await options.getAccessToken?.();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const requestId = await options.getRequestId?.();
  if (requestId) {
    headers.set("X-Request-ID", requestId);
  }
  return headers;
}

export function resolveTransportUrl(baseUrl: string, input: string): string {
  if (!baseUrl || /^(?:[a-z]+:)?\/\//iu.test(input)) {
    return input;
  }
  return `${baseUrl.replace(/\/$/u, "")}/${input.replace(/^\//u, "")}`;
}
