import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ActivatedRoute, UrlSegment, Router } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { of } from 'rxjs';
import { Component, Input } from '@angular/core';
import { HomePageComponent } from './home-page.component';
import { MatTabsModule } from '@angular/material/tabs';
import { provideAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { AuthService } from 'src/app/shared/services';
import { NavigationUrlService } from 'src/app/shared/services/navigation-url.service';
import { UserDataService } from 'src/app/shared/services/data/user-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { AccessKeyModalComponent } from 'src/app/shared/components';
import { RoutePath } from '../../home-page-routing.module';
import { TableColumnConfigModel } from 'src/app/shared/components/table/table.interface';

// Mock ml-table component
@Component({
  selector: 'ml-table',
  template: '<div>Mock Table</div>',
  standalone: false,
})
class MockTableComponent {
  @Input() columnConfig: TableColumnConfigModel[] = [];
  @Input() data: any[] = [];
}

describe('HomePageComponent', () => {
  let component: HomePageComponent;
  let fixture: ComponentFixture<HomePageComponent>;
  let authServiceMock: { getUserInfo: jest.Mock };
  let userDataServiceMock: {};
  let navigationUrlServiceMock: { navigateTo: jest.Mock };
  let matDialogMock: { open: jest.Mock };
  let routerMock: { navigate: jest.Mock };
  let activatedRouteMock: any;

  const mockUserInfo = {
    username: 'testuser',
    display_name: 'Test User',
    id: 42,
    is_admin: false,
    experiments: [
      {
        id: '1',
        name: 'Experiment 1',
        permission: 'read',
        type: 'basic'
      }
    ],
    models: [
      {
        id: 2,
        name: 'Model 2',
        permission: 'read',
        user_id: 42,
        type: 'basic'
      }
    ],
    prompts: [
      {
        id: 3,
        name: 'Prompt 3',
        permission: 'read',
        user_id: 42,
        type: 'basic'
      }
    ],
  };

  beforeEach(async () => {
    authServiceMock = { getUserInfo: jest.fn().mockReturnValue(mockUserInfo) };
    userDataServiceMock = {};
    navigationUrlServiceMock = { navigateTo: jest.fn() };
    matDialogMock = { open: jest.fn() };
    routerMock = { navigate: jest.fn() };
    activatedRouteMock = {
      params: of({ id: '123' }),
      queryParams: of({ filter: 'test' }),
      snapshot: {
        url: [new UrlSegment(RoutePath.Experiments, {})],
      },
    };

    await TestBed.configureTestingModule({
      imports: [RouterTestingModule, MatTabsModule],
      declarations: [HomePageComponent, MockTableComponent],
      providers: [
        provideHttpClientTesting(),
        provideHttpClient(),
        provideAnimations(),
        { provide: AuthService, useValue: authServiceMock },
        { provide: UserDataService, useValue: userDataServiceMock },
        { provide: NavigationUrlService, useValue: navigationUrlServiceMock },
        { provide: MatDialog, useValue: matDialogMock },
        { provide: Router, useValue: routerMock },
        { provide: ActivatedRoute, useValue: activatedRouteMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HomePageComponent);
    component = fixture.componentInstance;
    // Mock ViewChild
    component.userInfoTabs = { selectedIndex: 0 } as any;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize currentUserInfo and data sources in ngOnInit', () => {
    component.ngOnInit();
    expect(component.currentUserInfo).toEqual(mockUserInfo);
    expect(component.experimentsDataSource).toEqual(mockUserInfo.experiments);
    expect(component.modelsDataSource).toEqual(mockUserInfo.models);
    expect(component.promptsDataSource).toEqual(mockUserInfo.prompts);
  });

  it('should set selectedIndex in ngAfterViewInit based on route', () => {
    component.ngAfterViewInit();
    expect(component.userInfoTabs.selectedIndex).toBe(0); // RoutePath.Experiments is index 0
  });

  it('should open access key modal with correct data', () => {
    component.currentUserInfo = mockUserInfo;
    component.showAccessKeyModal();
    expect(matDialogMock.open).toHaveBeenCalledWith(AccessKeyModalComponent, {
      data: { username: 'testuser' },
    });
  });

  it('should call navigationUrlService.navigateTo with MLflow HOME url on redirectToMLFlow', () => {
    component.redirectToMLFlow();
    expect(navigationUrlServiceMock.navigateTo).toHaveBeenCalledWith(API_URL.HOME);
  });

  it('should navigate to correct tab path on handleTabSelection', async () => {
    await component.handleTabSelection(1);
    expect(routerMock.navigate).toHaveBeenCalledWith([`../${RoutePath.Models}`], {
      relativeTo: activatedRouteMock,
    });
  });

  it('should handle empty currentUserInfo gracefully in ngOnInit', () => {
    authServiceMock.getUserInfo.mockReturnValue(null);
    component.ngOnInit();
    expect(component.currentUserInfo).toBeNull();
    expect(component.experimentsDataSource).toEqual([]);
    expect(component.modelsDataSource).toEqual([]);
    expect(component.promptsDataSource).toEqual([]);
  });
});
