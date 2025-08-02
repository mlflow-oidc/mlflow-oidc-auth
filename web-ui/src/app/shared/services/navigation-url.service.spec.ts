import { NavigationUrlService } from './navigation-url.service';
import { DEFAULT_RUNTIME_CONFIG } from '../../core/models/runtime-config.interface';

describe('NavigationUrlService', () => {
  let service: NavigationUrlService;

  beforeEach(() => {
    service = new NavigationUrlService();
    // Reset global config before each test
    (window as any).__RUNTIME_CONFIG__ = undefined;
  });

  describe('getCurrentConfig', () => {
    it('should return DEFAULT_RUNTIME_CONFIG if global config is not set', () => {
      expect((service as any).getCurrentConfig()).toEqual(DEFAULT_RUNTIME_CONFIG);
    });

    it('should return global config if set', () => {
      const customConfig = { basePath: '/proxy', apiUrl: '/api' };
      (window as any).__RUNTIME_CONFIG__ = customConfig;
      expect((service as any).getCurrentConfig()).toEqual(customConfig);
    });
  });

  describe('buildNavigationUrl', () => {
    beforeEach(() => {
      (window as any).__RUNTIME_CONFIG__ = { basePath: '/proxy', apiUrl: '/api' };
    });

    it('should prefix path with basePath and handle leading slash', () => {
      expect(service.buildNavigationUrl('/logout')).toBe('/proxy/logout');
      expect(service.buildNavigationUrl('logout')).toBe('/proxy/logout');
    });

    it('should remove trailing slash from basePath', () => {
      (window as any).__RUNTIME_CONFIG__ = { basePath: '/proxy/', apiUrl: '/api' };
      expect(service.buildNavigationUrl('/admin')).toBe('/proxy/admin');
    });

    it('should remove double slashes except protocol', () => {
      (window as any).__RUNTIME_CONFIG__ = { basePath: '/proxy/', apiUrl: '/api' };
      expect(service.buildNavigationUrl('//admin')).toBe('/proxy/admin');
    });

    it('should handle empty path', () => {
      expect(service.buildNavigationUrl('')).toBe('/proxy/');
    });

    it('should handle basePath as root', () => {
      (window as any).__RUNTIME_CONFIG__ = { basePath: '/', apiUrl: '/api' };
      expect(service.buildNavigationUrl('/test')).toBe('/test');
    });
  });

  describe('navigateTo', () => {
    it('should set window.location.href to the built URL', () => {
      (window as any).__RUNTIME_CONFIG__ = { basePath: '/proxy', apiUrl: '/api' };
      const originalHref = window.location.href;
      let hrefValue = '';
      Object.defineProperty(window, 'location', {
        value: {
          get href() {
            return hrefValue;
          },
          set href(val: string) {
            hrefValue = val;
          }
        },
        writable: true
      });
      service.navigateTo('/logout');
      expect(hrefValue).toBe('/proxy/logout');
      // Restore original location if needed
      Object.defineProperty(window, 'location', {
        value: { href: originalHref },
        writable: true
      });
    });
  });
});
