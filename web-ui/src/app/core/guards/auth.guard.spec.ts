import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { RuntimeConfigService } from '../services/runtime-config.service';
import { AuthGuard } from './auth.guard';
import { RoutePath } from '../configs/core';

describe('AuthGuard', () => {
  let guard: AuthGuard;
  let mockRouter: any;
  let mockRuntimeConfigService: any;

  beforeEach(() => {
    const routerSpy = jasmine.createSpyObj('Router', ['navigate']);
    const configServiceSpy = jasmine.createSpyObj('RuntimeConfigService', ['getCurrentConfig']);

    TestBed.configureTestingModule({
      providers: [
        AuthGuard,
        { provide: Router, useValue: routerSpy },
        { provide: RuntimeConfigService, useValue: configServiceSpy }
      ]
    });

    guard = TestBed.inject(AuthGuard);
    mockRouter = TestBed.inject(Router);
    mockRuntimeConfigService = TestBed.inject(RuntimeConfigService);
  });

  it('should be created', () => {
    expect(guard).toBeTruthy();
  });

  it('should allow access when authenticated', () => {
    mockRuntimeConfigService.getCurrentConfig.and.returnValue({
      basePath: '',
      uiPath: '',
      authenticated: true,
      provider: 'Test'
    });

    expect(guard.canActivate()).toBe(true);
    expect(mockRouter.navigate).not.toHaveBeenCalled();
  });

  it('should deny access and redirect when not authenticated', () => {
    mockRuntimeConfigService.getCurrentConfig.and.returnValue({
      basePath: '',
      uiPath: '',
      authenticated: false,
      provider: 'Test'
    });

    expect(guard.canActivate()).toBe(false);
    expect(mockRouter.navigate).toHaveBeenCalledWith([RoutePath.Auth], { replaceUrl: true });
  });
});
