import { Injectable } from '@angular/core';
import { HttpInterceptor, HttpRequest, HttpHandler, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';
import { RuntimeConfig, DEFAULT_RUNTIME_CONFIG } from '../models/runtime-config.interface';

/**
 * HTTP Interceptor that automatically adds the proxy base path to API requests.
 *
 * This interceptor ensures that all HTTP requests are properly prefixed
 * with the dynamic base path when the application is running behind a proxy.
 */
@Injectable()
export class RuntimeConfigInterceptor implements HttpInterceptor {
  /**
   * Get the current runtime configuration from global scope
   */
  private getCurrentConfig(): RuntimeConfig {
    return (window as any).__RUNTIME_CONFIG__ || DEFAULT_RUNTIME_CONFIG;
  }

  /**
   * Build a complete URL with the current base path
   *
   * @param path - The relative path to append
   * @returns Complete URL with base path
   */
  private buildUrl(path: string): string {
    const config = this.getCurrentConfig();
    const basePath = config.basePath.endsWith('/') ? config.basePath.slice(0, -1) : config.basePath;
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${basePath}${cleanPath}`;
  }

  /**
   * Intercept HTTP requests and modify URLs based on runtime configuration
   *
   * @param req - The outgoing HTTP request
   * @param next - The next handler in the chain
   * @returns Observable of the HTTP event
   */
  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    const config = this.getCurrentConfig();

    // Skip modification for absolute URLs or already prefixed URLs
    if (this.isAbsoluteUrl(req.url) || this.isAlreadyPrefixed(req.url, config.basePath)) {
      return next.handle(req);
    }

    // Skip modification for the runtime config endpoint to avoid circular calls
    if (req.url.includes('config.json')) {
      return next.handle(req);
    }

    // Add base path to relative API URLs
    let modifiedUrl = req.url;
    if (config.basePath) {
      modifiedUrl = this.buildUrl(req.url);
    }

    // Clone the request with the modified URL
    const modifiedReq = req.clone({
      url: modifiedUrl
    });

    return next.handle(modifiedReq);
  }

  /**
   * Check if a URL is absolute (contains protocol and host)
   *
   * @param url - The URL to check
   * @returns True if the URL is absolute
   */
  private isAbsoluteUrl(url: string): boolean {
    return /^https?:\/\//.test(url);
  }

  /**
   * Check if a URL is already prefixed with the base path
   *
   * @param url - The URL to check
   * @param basePath - The base path to check for
   * @returns True if the URL already contains the base path
   */
  private isAlreadyPrefixed(url: string, basePath: string): boolean {
    if (!basePath) {
      return false;
    }
    return url.startsWith(basePath);
  }
}
