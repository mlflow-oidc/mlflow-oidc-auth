import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RuntimeConfigService } from './runtime-config.service';
import { RuntimeConfig } from '../models/runtime-config.interface';

describe('RuntimeConfigService', () => {
  let service: RuntimeConfigService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [RuntimeConfigService]
    });
    service = TestBed.inject(RuntimeConfigService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should load config successfully', () => {
    const mockConfig: RuntimeConfig = {
      basePath: '/test',
      uiPath: '/test/oidc/ui',
      provider: 'Test Provider',
      authenticated: true
    };

    service.loadConfig().subscribe(config => {
      expect(config).toEqual(mockConfig);
      expect(service.getCurrentConfig()).toEqual(mockConfig);
      expect(service.isAuthenticated()).toBe(true);
    });

    const req = httpMock.expectOne('config.json');
    expect(req.request.method).toBe('GET');
    req.flush(mockConfig);
  });

  it('should handle config load error and return fallback', () => {
    service.loadConfig().subscribe(config => {
      expect(config.authenticated).toBe(false);
      expect(config.provider).toBe('Login with Test');
      expect(service.isAuthenticated()).toBe(false);
    });

    const req = httpMock.expectOne('config.json');
    req.error(new ErrorEvent('Network error'));
  });

  it('should check authentication status', () => {
    expect(service.isAuthenticated()).toBe(false); // Default

    const mockConfig: RuntimeConfig = {
      basePath: '',
      uiPath: '',
      provider: 'Test',
      authenticated: true
    };

    service.loadConfig().subscribe();
    const req = httpMock.expectOne('config.json');
    req.flush(mockConfig);

    expect(service.isAuthenticated()).toBe(true);
  });
});
