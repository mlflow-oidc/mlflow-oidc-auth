import { RuntimeConfigInterceptor } from './runtime-config.interceptor';
import { HttpRequest, HttpHandler, HttpEvent, HttpResponse } from '@angular/common/http';
import { DEFAULT_RUNTIME_CONFIG } from '../models/runtime-config.interface';
import { of } from 'rxjs';

describe('RuntimeConfigInterceptor', () => {
    let interceptor: RuntimeConfigInterceptor;
    let handler: HttpHandler;

    beforeEach(() => {
        interceptor = new RuntimeConfigInterceptor();
        handler = {
            handle: jest.fn((req: HttpRequest<any>) => of(new HttpResponse({ status: 200, url: req.url })))
        };
        window.__RUNTIME_CONFIG__ = undefined;
    });

    it('should use DEFAULT_RUNTIME_CONFIG if global config is not set', () => {
        expect((interceptor as any).getCurrentConfig()).toEqual(DEFAULT_RUNTIME_CONFIG);
    });

    it('should use global __RUNTIME_CONFIG__ if set', () => {
        window.__RUNTIME_CONFIG__ = { basePath: '/proxy', uiPath: '/ui' };
        expect((interceptor as any).getCurrentConfig().basePath).toBe('/proxy');
    });

    it('should build URL with basePath and relative path', () => {
        window.__RUNTIME_CONFIG__ = { basePath: '/proxy', uiPath: '/ui' };
        expect((interceptor as any).buildUrl('api/test')).toBe('/proxy/api/test');
    });

    it('should build URL with basePath and absolute path', () => {
        window.__RUNTIME_CONFIG__ = { basePath: '/proxy/', uiPath: '/ui' };
        expect((interceptor as any).buildUrl('/api/test')).toBe('/proxy/api/test');
    });

    it('should not modify absolute URLs', () => {
        const req = new HttpRequest('GET', 'https://external.com/api');
        interceptor.intercept(req, handler).subscribe();
        expect(handler.handle).toHaveBeenCalledWith(req);
    });

    it('should not modify already prefixed URLs', () => {
        window.__RUNTIME_CONFIG__ = { basePath: '/proxy', uiPath: '/ui' };
        const req = new HttpRequest('GET', '/proxy/api/test');
        interceptor.intercept(req, handler).subscribe();
        expect(handler.handle).toHaveBeenCalledWith(req);
    });

    it('should not modify config.json requests', () => {
        const req = new HttpRequest('GET', '/assets/config.json');
        interceptor.intercept(req, handler).subscribe();
        expect(handler.handle).toHaveBeenCalledWith(req);
    });

    it('should add basePath to relative URLs', () => {
        window.__RUNTIME_CONFIG__ = { basePath: '/proxy', uiPath: '/ui' };
        const req = new HttpRequest('GET', 'api/test');
        interceptor.intercept(req, handler).subscribe((event: HttpEvent<any>) => {
            expect((event as HttpResponse<any>).url).toBe('/proxy/api/test');
        });
    });

    it('should handle empty basePath gracefully', () => {
        window.__RUNTIME_CONFIG__ = { basePath: '', uiPath: '/ui' };
        const req = new HttpRequest('GET', 'api/test');
        interceptor.intercept(req, handler).subscribe((event: HttpEvent<any>) => {
            expect((event as HttpResponse<any>).url).toBe('api/test');
        });
    });

    it('isAbsoluteUrl should detect absolute URLs', () => {
        expect((interceptor as any).isAbsoluteUrl('http://test')).toBe(true);
        expect((interceptor as any).isAbsoluteUrl('https://test')).toBe(true);
        expect((interceptor as any).isAbsoluteUrl('/api/test')).toBe(false);
        expect((interceptor as any).isAbsoluteUrl('api/test')).toBe(false);
    });

    it('isAlreadyPrefixed should detect prefixed URLs', () => {
        const interceptor = new RuntimeConfigInterceptor();
        expect((interceptor as any).isAlreadyPrefixed('/proxy/api', '/proxy')).toBe(true);
        expect((interceptor as any).isAlreadyPrefixed('/api', '/proxy')).toBe(false);
        expect((interceptor as any).isAlreadyPrefixed('/api', '')).toBe(false);
    });
});
