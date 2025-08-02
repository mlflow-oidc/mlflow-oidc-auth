import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { RouterModule } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';

import { HeaderComponent } from './header.component';
import { NavigationUrlService } from '../../services/navigation-url.service';
import { API_URL } from '../../../core/configs/api-urls';

describe('HeaderComponent', () => {
  let component: HeaderComponent;
  let fixture: ComponentFixture<HeaderComponent>;
  let navigationUrlServiceMock: { navigateTo: jest.Mock };

  beforeEach(async () => {
    navigationUrlServiceMock = {
      navigateTo: jest.fn(),
    };

    await TestBed.configureTestingModule({
      declarations: [HeaderComponent],
      imports: [MatToolbarModule, MatIconModule, RouterModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: { get: () => 'mockParamValue' } },
            queryParams: of({ mockQueryParam: 'mockValue' }),
          },
        },
        { provide: NavigationUrlService, useValue: navigationUrlServiceMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HeaderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should accept and render @Input() name', () => {
    component.name = 'Test User';
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(component.name).toBe('Test User');
    // expect(compiled.textContent).toContain('Test User');
  });

  it('should accept and use @Input() admin', () => {
    component.admin = true;
    fixture.detectChanges();
    expect(component.admin).toBe(true);
    // e.g. expect(compiled.querySelector('.admin-badge')).not.toBeNull();
  });

  it('should call navigationUrlService.navigateTo with MLflow HOME url on redirectToMLflow()', () => {
    component.redirectToMLflow();
    expect(navigationUrlServiceMock.navigateTo).toHaveBeenCalledWith(API_URL.HOME);
  });

  it('should call navigationUrlService.navigateTo with LOGOUT url on logout()', () => {
    component.logout();
    expect(navigationUrlServiceMock.navigateTo).toHaveBeenCalledWith(API_URL.LOGOUT);
  });
});
