import { RuntimeConfig } from '../models/runtime-config.interface';

/**
 * Service responsible for loading runtime configuration before Angular bootstrap.
 *
 * This service handles the special case of loading configuration when Angular
 * services are not yet available, using plain fetch API and relative paths.
 */
export class BootstrapConfigService {

    /**
     * Load runtime configuration before Angular application bootstrap.
     * This ensures that proxy path configuration is available before the app starts.
     *
     * The config endpoint is served under the same path as the UI, so we can use
     * a simple relative path that works regardless of proxy configuration.
     */
    public async loadRuntimeConfig(): Promise<RuntimeConfig> {
        try {
            // Use relative path - works because config.json is served from same UI path
            const response = await fetch('config.json');

            if (response.ok) {
                const config = await response.json();
                return config;
            } else {
                console.warn(`Failed to load runtime config: HTTP ${response.status}`);
            }
        } catch (error) {
            console.warn('Failed to load runtime config:', error);
        }

        // Fallback: infer configuration from current URL
        return this.inferConfigFromCurrentUrl();
    }

    /**
     * Infer runtime configuration from the current URL when all fetch attempts fail
     */
    private inferConfigFromCurrentUrl(): RuntimeConfig {
        const currentPath = window.location.pathname;
        const segments = currentPath.split('/').filter(segment => segment.length > 0);

        // Try to detect common patterns
        let inferredBasePath = '';

        // If current path contains 'oidc/ui', assume everything before that is the prefix
        const oidcIndex = segments.findIndex(segment => segment === 'oidc');
        if (oidcIndex > 0) {
            inferredBasePath = `/${segments.slice(0, oidcIndex).join('/')}`;
        }
        // If current path has multiple segments, assume first segment might be the prefix
        else if (segments.length > 0 && segments[0] !== 'oidc') {
            inferredBasePath = `/${segments[0]}`;
        }

        return {
            basePath: inferredBasePath,
            uiPath: `${inferredBasePath}/oidc/ui`,
        };
    }

    /**
     * Update the base href in the document head
     */
    public updateBaseHref(basePath: string): void {
        const normalizedBasePath = basePath.endsWith('/') ? basePath : `${basePath}/`;

        let baseTag = document.querySelector('base') as HTMLBaseElement;
        if (!baseTag) {
            baseTag = document.createElement('base');
            const head = document.querySelector('head');
            if (head) {
                head.appendChild(baseTag);
            }
        }

        baseTag.href = normalizedBasePath;
    }
}
