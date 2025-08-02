import { BootstrapConfigService } from './bootstrap-config.service';
import { RuntimeConfig } from '../models/runtime-config.interface';

describe('BootstrapConfigService', () => {
    let service: BootstrapConfigService;

    beforeEach(() => {
        service = new BootstrapConfigService();
        // Reset window.location.pathname for each test
        Object.defineProperty(window, 'location', {
            value: { pathname: '/proxy/oidc/ui' },
            writable: true
        });
        document.head.innerHTML = '';
    });

    describe('loadRuntimeConfig', () => {
        it('should return config from fetch if response is ok', async () => {
            const mockConfig = { basePath: '/proxy', uiPath: '/proxy/oidc/ui' };
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                json: jest.fn().mockResolvedValue(mockConfig)
            } as any);

            const config = await service.loadRuntimeConfig();
            expect(config).toEqual(mockConfig);
        });

        it('should warn and fallback if fetch response is not ok', async () => {
            global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 404 } as any);
            const spy = jest.spyOn(console, 'warn').mockImplementation(() => { });
            const config = await service.loadRuntimeConfig();
            expect(spy).toHaveBeenCalledWith('Failed to load runtime config: HTTP 404');
            expect(config).toEqual(service['inferConfigFromCurrentUrl']());
            spy.mockRestore();
        });

        it('should warn and fallback if fetch throws', async () => {
            global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));
            const spy = jest.spyOn(console, 'warn').mockImplementation(() => { });
            const config = await service.loadRuntimeConfig();
            expect(spy).toHaveBeenCalledWith('Failed to load runtime config:', expect.any(Error));
            expect(config).toEqual(service['inferConfigFromCurrentUrl']());
            spy.mockRestore();
        });
    });

    describe('inferConfigFromCurrentUrl', () => {
        it('should infer basePath from /proxy/oidc/ui', () => {
            window.location.pathname = '/proxy/oidc/ui';
            const config = service['inferConfigFromCurrentUrl']();
            expect(config.basePath).toBe('/proxy');
            expect(config.uiPath).toBe('/proxy/oidc/ui');
        });

        it('should infer basePath from /other/oidc/ui', () => {
            window.location.pathname = '/other/oidc/ui';
            const config = service['inferConfigFromCurrentUrl']();
            expect(config.basePath).toBe('/other');
            expect(config.uiPath).toBe('/other/oidc/ui');
        });

        it('should infer basePath from /oidc/ui', () => {
            window.location.pathname = '/oidc/ui';
            const config = service['inferConfigFromCurrentUrl']();
            expect(config.basePath).toBe('');
            expect(config.uiPath).toBe('/oidc/ui');
        });

        it('should infer basePath from /foo/bar', () => {
            window.location.pathname = '/foo/bar';
            const config = service['inferConfigFromCurrentUrl']();
            expect(config.basePath).toBe('/foo');
            expect(config.uiPath).toBe('/foo/oidc/ui');
        });

        it('should infer basePath from /', () => {
            window.location.pathname = '/';
            const config = service['inferConfigFromCurrentUrl']();
            expect(config.basePath).toBe('');
            expect(config.uiPath).toBe('/oidc/ui');
        });
    });

    describe('updateBaseHref', () => {
        it('should create base tag if not present and set href', () => {
            expect(document.querySelector('base')).toBeNull();
            service.updateBaseHref('/proxy');
            const baseTag = document.querySelector('base') as HTMLBaseElement;
            expect(baseTag).not.toBeNull();
            expect(baseTag.href).toMatch(/\/proxy\/$/);
        });

        it('should update existing base tag href', () => {
            const baseTag = document.createElement('base');
            document.head.appendChild(baseTag);
            service.updateBaseHref('/proxy');
            expect(baseTag.href).toMatch(/\/proxy\/$/);
        });

        it('should normalize basePath with trailing slash', () => {
            service.updateBaseHref('/proxy/');
            const baseTag = document.querySelector('base') as HTMLBaseElement;
            expect(baseTag.href).toMatch(/\/proxy\/$/);
        });
    });
});
