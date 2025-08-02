import { enableProdMode } from '@angular/core';
import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';

import { AppModule } from './app/app.module';
import { environment } from './environments/environment';
import { BootstrapConfigService } from './app/core/services/bootstrap-config.service';

/**
 * Bootstrap the Angular application with runtime configuration
 */
async function bootstrap(): Promise<void> {
  if (environment.production) {
    enableProdMode();
  }

  // Create bootstrap service instance (pre-Angular)
  const bootstrapService = new BootstrapConfigService();

  // Load runtime configuration before bootstrapping
  const runtimeConfig = await bootstrapService.loadRuntimeConfig();

  // Update the document base href to point to the UI path
  if (runtimeConfig.uiPath) {
    bootstrapService.updateBaseHref(runtimeConfig.uiPath);
  }

  // Store the configuration globally for services to access
  window.__RUNTIME_CONFIG__ = runtimeConfig;

  // Bootstrap the Angular application
  try {
    await platformBrowserDynamic().bootstrapModule(AppModule);
  } catch (err) {
    console.error('Failed to bootstrap Angular application:', err);
  }
}

// Start the bootstrap process
bootstrap();
