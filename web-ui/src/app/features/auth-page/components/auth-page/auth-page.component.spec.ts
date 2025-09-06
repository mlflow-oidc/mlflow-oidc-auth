import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { AuthPageComponent } from './auth-page.component';

describe('AuthPageComponent', () => {
  let component: AuthPageComponent;
  let fixture: ComponentFixture<AuthPageComponent>;
  let mockActivatedRoute: Partial<ActivatedRoute>;

  beforeEach(async () => {
    mockActivatedRoute = {
      snapshot: {
        data: { config: { basePath: '/test', provider: 'Test Provider' } },
        queryParams: {}
      } as any
    };

    await TestBed.configureTestingModule({
      declarations: [AuthPageComponent],
      imports: [
        MatButtonModule,
        MatIconModule,
        NoopAnimationsModule
      ],
      providers: [
        { provide: ActivatedRoute, useValue: mockActivatedRoute }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(AuthPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should set config from route data', () => {
    expect(component.config).toEqual({ basePath: '/test', provider: 'Test Provider' });
  });

  it('should construct correct login URL', () => {
    expect(component.loginUrl).toBe('/test/login');
  });

  it('should return provider display name', () => {
    expect(component.providerDisplayName).toBe('Test Provider');
  });

  it('should fallback to default provider name when not provided', () => {
    component.config = { basePath: '', uiPath: '', authenticated: false };
    expect(component.providerDisplayName).toBe('Login with Test');
  });

  it('should handle error messages from query params', () => {
    const mockRoute = {
      snapshot: {
        data: {},
        queryParams: { error: ['Error 1', 'Error 2'] }
      }
    };
    TestBed.overrideProvider(ActivatedRoute, { useValue: mockRoute });

    const newFixture = TestBed.createComponent(AuthPageComponent);
    const newComponent = newFixture.componentInstance;
    newComponent.ngOnInit();

    expect(newComponent.processedErrors.length).toBe(2);
    expect(newComponent.hasErrors).toBe(true);
  });

  it('should decode URL-encoded error messages', () => {
    const encodedError = 'OIDC%20provider%20error%3A%20An%20error%20occurred%20during%20the%20OIDC%20authentication%20process.';
    const mockRoute = {
      snapshot: {
        data: {},
        queryParams: { error: [encodedError] }
      }
    };
    TestBed.overrideProvider(ActivatedRoute, { useValue: mockRoute });

    const newFixture = TestBed.createComponent(AuthPageComponent);
    const newComponent = newFixture.componentInstance;
    newComponent.ngOnInit();

    expect(newComponent.processedErrors[0].message).toBe('An error occurred during the OIDC authentication process.');
    expect(newComponent.processedErrors[0].type).toBe('provider');
  });

  it('should categorize security errors correctly', () => {
    const securityError = 'Security error: Invalid state parameter. Possible CSRF detected.';
    const mockRoute = {
      snapshot: {
        data: {},
        queryParams: { error: [securityError] }
      }
    };
    TestBed.overrideProvider(ActivatedRoute, { useValue: mockRoute });

    const newFixture = TestBed.createComponent(AuthPageComponent);
    const newComponent = newFixture.componentInstance;
    newComponent.ngOnInit();

    expect(newComponent.processedErrors[0].type).toBe('security');
    expect(newComponent.processedErrors[0].severity).toBe('error');
    expect(newComponent.getErrorIcon('security')).toBe('security');
  });

  it('should categorize authorization errors correctly', () => {
    const authError = 'Authorization error: User is not allowed to login.';
    const mockRoute = {
      snapshot: {
        data: {},
        queryParams: { error: [authError] }
      }
    };
    TestBed.overrideProvider(ActivatedRoute, { useValue: mockRoute });

    const newFixture = TestBed.createComponent(AuthPageComponent);
    const newComponent = newFixture.componentInstance;
    newComponent.ngOnInit();

    expect(newComponent.processedErrors[0].type).toBe('authorization');
    expect(newComponent.getErrorIcon('authorization')).toBe('block');
  });

  it('should provide appropriate actions for different error types', () => {
    const sessionError = 'Session error: Missing OAuth state in session. Please try logging in again.';
    const mockRoute = {
      snapshot: {
        data: {},
        queryParams: { error: [sessionError] }
      }
    };
    TestBed.overrideProvider(ActivatedRoute, { useValue: mockRoute });

    const newFixture = TestBed.createComponent(AuthPageComponent);
    const newComponent = newFixture.componentInstance;
    newComponent.ngOnInit();

    expect(newComponent.processedErrors[0].type).toBe('session');
    expect(newComponent.processedErrors[0].action).toContain('clear your browser cache');
  });

  it('should clear errors when clearErrors is called', () => {
    const mockRoute = {
      snapshot: {
        data: {},
        queryParams: { error: ['Error 1'] }
      }
    };
    TestBed.overrideProvider(ActivatedRoute, { useValue: mockRoute });

    const newFixture = TestBed.createComponent(AuthPageComponent);
    const newComponent = newFixture.componentInstance;
    newComponent.ngOnInit();

    expect(newComponent.hasErrors).toBe(true);

    newComponent.clearErrors();

    expect(newComponent.hasErrors).toBe(false);
    expect(newComponent.processedErrors.length).toBe(0);
  });

  it('should handle malformed encoded errors gracefully', () => {
    const malformedError = '%GG%invalid%encoded%string';
    const mockRoute = {
      snapshot: {
        data: {},
        queryParams: { error: [malformedError] }
      }
    };
    TestBed.overrideProvider(ActivatedRoute, { useValue: mockRoute });

    const newFixture = TestBed.createComponent(AuthPageComponent);
    const newComponent = newFixture.componentInstance;
    newComponent.ngOnInit();

    expect(newComponent.processedErrors.length).toBe(1);
    expect(newComponent.processedErrors[0].message).toBe('An unexpected error occurred during authentication.');
    expect(newComponent.processedErrors[0].type).toBe('general');
  });
});
