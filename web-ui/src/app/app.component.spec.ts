import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { AppComponent } from './app.component';
import { SharedModule } from './shared/shared.module';
import { FooterComponent } from './shared/components/footer/footer.component';
import { RuntimeConfigService } from './core/services/runtime-config.service';
import { of } from 'rxjs';
import { RuntimeConfig } from './core/models/runtime-config.interface';

describe('AppComponent', () => {
  let mockRuntimeConfigService: Partial<RuntimeConfigService>;

  beforeEach(async () => {
    const mockConfig: RuntimeConfig = {
      basePath: '',
      uiPath: '/oidc/ui',
      provider: 'Test Provider',
      authenticated: true
    };

    mockRuntimeConfigService = {
      loadConfig: jasmine.createSpy('loadConfig').and.returnValue(of(mockConfig)),
      getCurrentConfig: jasmine.createSpy('getCurrentConfig').and.returnValue(mockConfig),
      isAuthenticated: jasmine.createSpy('isAuthenticated').and.returnValue(true),
      config$: of(mockConfig)
    };

    await TestBed.configureTestingModule({
      imports: [
        SharedModule,
        FooterComponent,
      ],
      declarations: [AppComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: RuntimeConfigService, useValue: mockRuntimeConfigService }
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should load runtime config on init', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;

    app.ngOnInit();

    expect(mockRuntimeConfigService.loadConfig).toHaveBeenCalled();
  });
});
