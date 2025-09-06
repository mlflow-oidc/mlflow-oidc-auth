/**
 * Interface for runtime configuration received from the backend
 */
export interface RuntimeConfig {
    basePath: string;
    uiPath: string;
    provider?: string;
    authenticated: boolean;
}

/**
 * Default configuration used as fallback
 */
export const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
    basePath: '',
    uiPath: '/oidc/ui',
    provider: 'Login with Test',
    authenticated: false,
};
