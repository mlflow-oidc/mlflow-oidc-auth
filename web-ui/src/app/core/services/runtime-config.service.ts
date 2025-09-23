import { Injectable } from '@angular/core';
import { Observable, of, BehaviorSubject } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { catchError, map } from 'rxjs/operators';
import { RuntimeConfig, DEFAULT_RUNTIME_CONFIG } from '../models/runtime-config.interface';

@Injectable({
  providedIn: 'root'
})
export class RuntimeConfigService {
  private configSubject = new BehaviorSubject<RuntimeConfig>(DEFAULT_RUNTIME_CONFIG);
  public config$ = this.configSubject.asObservable();

  constructor(private http: HttpClient) {
    // Initialize with global config if available
    const globalConfig = window.__RUNTIME_CONFIG__;
    if (globalConfig) {
      this.configSubject.next(globalConfig);
    }
  }

  /**
   * Load runtime configuration from backend
   */
  loadConfig(): Observable<RuntimeConfig> {
    // If we already have global config, use it
    const globalConfig = window.__RUNTIME_CONFIG__;
    if (globalConfig) {
      this.configSubject.next(globalConfig);
      return of(globalConfig);
    }

    return this.http.get<RuntimeConfig>('config.json').pipe(
      map((config) => {
        this.configSubject.next(config);
        return config;
      }),
      catchError((error) => {
        console.warn('Failed to load runtime config:', error);
        const fallbackConfig = this.inferConfigFromCurrentUrl();
        this.configSubject.next(fallbackConfig);
        return of(fallbackConfig);
      })
    );
  }

  /**
   * Get current config synchronously
   */
  getCurrentConfig(): RuntimeConfig {
    return this.configSubject.value;
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return this.configSubject.value.authenticated;
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
      authenticated: false, // Default to not authenticated when config fails to load
      provider: 'Login with Test'
    };
  }
}
