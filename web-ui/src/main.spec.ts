import { enableProdMode } from '@angular/core';
import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';
import { environment } from './environments/environment';
import { BootstrapConfigService } from './app/core/services/bootstrap-config.service';

// Create mock functions that can be accessed in tests
const mockLoadRuntimeConfig = jest.fn();
const mockUpdateBaseHref = jest.fn();

// Mock dependencies
jest.mock('@angular/core', () => ({
  enableProdMode: jest.fn(),
}));
jest.mock('@angular/platform-browser-dynamic', () => ({
  platformBrowserDynamic: jest.fn(() => ({
    bootstrapModule: jest.fn(),
  })),
}));
jest.mock('./app/app.module', () => ({}));
jest.mock('./environments/environment', () => ({
  environment: { production: false },
}));
jest.mock('./app/core/services/bootstrap-config.service', () => {
  return {
    BootstrapConfigService: jest.fn().mockImplementation(() => ({
      loadRuntimeConfig: mockLoadRuntimeConfig,
      updateBaseHref: mockUpdateBaseHref,
    })),
  };
});

// Create a testable version of the bootstrap function
async function createBootstrapFunction(): Promise<void> {
  if (environment.production) {
    enableProdMode();
  }

  // Create bootstrap service instance (pre-Angular)
  const bootstrapService = new BootstrapConfigService();

  // Load runtime configuration before bootstrapping
  const runtimeConfig = await bootstrapService.loadRuntimeConfig();

  // Update the document base href to point to the UI path
  if (runtimeConfig && runtimeConfig.uiPath) {
    bootstrapService.updateBaseHref(runtimeConfig.uiPath);
  }

  // Store the configuration globally for services to access
  (window as any).__RUNTIME_CONFIG__ = runtimeConfig;

  // Bootstrap the Angular application
  try {
    await platformBrowserDynamic().bootstrapModule(AppModule);
  } catch (err) {
    console.error('Failed to bootstrap Angular application:', err);
  }
}

describe('main.ts bootstrap', () => {
  let mockRuntimeConfig: any;
  let mockBootstrapModule: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();

    mockRuntimeConfig = { uiPath: '/test-ui', basePath: '/test' };

    // Create a fresh mock for bootstrapModule
    mockBootstrapModule = jest.fn().mockResolvedValue({});

    // Setup mock for platformBrowserDynamic
    (platformBrowserDynamic as jest.Mock).mockReturnValue({
      bootstrapModule: mockBootstrapModule,
    });

    // Setup default mock return values
    mockLoadRuntimeConfig.mockResolvedValue(mockRuntimeConfig);
    mockUpdateBaseHref.mockImplementation(() => {});

    (window as any).__RUNTIME_CONFIG__ = undefined;
  });

  it('should enable prod mode if environment.production is true', async () => {
    require('./environments/environment').environment.production = true;
    await createBootstrapFunction();
    expect(enableProdMode).toHaveBeenCalled();
  });

  it('should not enable prod mode if environment.production is false', async () => {
    require('./environments/environment').environment.production = false;
    await createBootstrapFunction();
    expect(enableProdMode).not.toHaveBeenCalled();
  });

  it('should load runtime config and update base href if uiPath exists', async () => {
    await createBootstrapFunction();
    expect(mockLoadRuntimeConfig).toHaveBeenCalled();
    expect(mockUpdateBaseHref).toHaveBeenCalledWith('/test-ui');
    expect((window as any).__RUNTIME_CONFIG__).toEqual(mockRuntimeConfig);
  });

  it('should not update base href if uiPath does not exist', async () => {
    mockLoadRuntimeConfig.mockResolvedValue({});
    await createBootstrapFunction();
    expect(mockUpdateBaseHref).not.toHaveBeenCalled();
  });

  it('should bootstrap Angular application', async () => {
    await createBootstrapFunction();
    expect(mockBootstrapModule).toHaveBeenCalledWith(AppModule);
  });

  it('should handle bootstrap errors gracefully', async () => {
    const error = new Error('Bootstrap failed');
    mockBootstrapModule.mockRejectedValueOnce(error);
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    await createBootstrapFunction();
    expect(consoleSpy).toHaveBeenCalledWith('Failed to bootstrap Angular application:', error);
    consoleSpy.mockRestore();
  });
});
