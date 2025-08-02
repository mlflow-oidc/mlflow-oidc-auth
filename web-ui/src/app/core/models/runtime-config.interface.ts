/**
 * Interface for runtime configuration received from the backend
 */
export interface RuntimeConfig {
    basePath: string;
    uiPath: string;
}

/**
 * Default configuration used as fallback
 */
export const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
    basePath: '',
    uiPath: '/oidc/ui',
};
