import { Injectable } from '@angular/core';
import { RuntimeConfig, DEFAULT_RUNTIME_CONFIG } from '../../core/models/runtime-config.interface';

/**
 * Service for building navigation URLs that require proxy path prefixing.
 *
 * This service provides a consistent way to build URLs for browser navigation
 * (window.location.href) that properly handle proxy path configurations.
 *
 * Note: This is different from HTTP requests which are automatically handled
 * by the RuntimeConfigInterceptor.
 */
@Injectable({
    providedIn: 'root'
})
export class NavigationUrlService {
    /**
     * Get the current runtime configuration from global scope
     */
    private getCurrentConfig(): RuntimeConfig {
        return (window as any).__RUNTIME_CONFIG__ || DEFAULT_RUNTIME_CONFIG;
    }

    /**
     * Build a navigation URL with proper proxy path prefixing
     *
     * @param path - The path to navigate to (e.g., '/logout', '/admin')
     * @returns Complete URL with proxy path prefix
     */
    public buildNavigationUrl(path: string): string {
        const config = this.getCurrentConfig();
        const basePath = config.basePath.endsWith('/') ? config.basePath.slice(0, -1) : config.basePath;
        const cleanPath = path.startsWith('/') ? path : `/${path}`;
        const fullUrl = `${basePath}${cleanPath}`;

        // Remove double slashes (except for protocol://)
        return fullUrl.replace(/([^:]\/)\/+/g, '$1');
    }

    /**
     * Navigate to a URL with proper proxy path handling
     *
     * @param path - The path to navigate to
     */
    public navigateTo(path: string): void {
        window.location.href = this.buildNavigationUrl(path);
    }
}
