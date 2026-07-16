import axios, {
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';

type RetryableConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
  _retryCount?: number;
};

const env = import.meta.env as ImportMetaEnv & Record<string, string | undefined>;

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const configuredBaseUrl =
  env.NEXT_PUBLIC_API_URL ||
  env.VITE_API_URL ||
  'http://localhost:8000';

const rootUrl = trimTrailingSlash(configuredBaseUrl);
export const API_ROOT_URL = rootUrl.replace(/\/api\/v1$/, '');
export const API_BASE_URL = rootUrl.endsWith('/api/v1') ? rootUrl : `${rootUrl}/api/v1`;

const ACCESS_TOKEN_KEY = 'fios_access_token';
const REFRESH_TOKEN_KEY = 'fios_refresh_token';
const LEGACY_ACCESS_TOKEN_KEY = 'fios_token';

export const tokenStore = {
  getAccessToken: () =>
    localStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem(LEGACY_ACCESS_TOKEN_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (accessToken: string, refreshToken?: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
    if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
  },
};

export const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.request.use((config) => {
  const token = tokenStore.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

const refreshAccessToken = async () => {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshToken = tokenStore.getRefreshToken();
      if (!refreshToken) return null;

      const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      });
      tokenStore.setTokens(response.data.access_token, response.data.refresh_token);
      return response.data.access_token as string;
    })().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
};

const retryDelay = (retryCount: number) =>
  new Promise((resolve) => window.setTimeout(resolve, retryCount * 350));

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryableConfig | undefined;
    if (!config) throw error;

    if (error.response?.status === 401 && !config._retry) {
      config._retry = true;
      let accessToken: string | null = null;
      try {
        accessToken = await refreshAccessToken();
      } catch {
        accessToken = null;
      }
      if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
        return client(config);
      }
      tokenStore.clear();
      // Session is unrecoverable: tell the app shell to fall back to the login screen.
      window.dispatchEvent(new CustomEvent('fios:unauthorized'));
    }

    const retryCount = config._retryCount ?? 0;
    const isRetryable =
      !error.response || (error.response.status >= 500 && error.response.status < 600);

    if (isRetryable && retryCount < 2) {
      config._retryCount = retryCount + 1;
      await retryDelay(config._retryCount);
      return client(config);
    }

    throw error;
  },
);

export const apiRequest = async <T>(config: AxiosRequestConfig): Promise<T> => {
  const response = await client.request<T>(config);
  return response.data;
};

export const buildDocsUrl = () => `${API_ROOT_URL}/docs`;
