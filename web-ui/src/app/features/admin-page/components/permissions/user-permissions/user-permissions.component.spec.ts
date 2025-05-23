import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of, throwError } from 'rxjs';
import { provideHttpClient } from '@angular/common/http';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTabsModule } from '@angular/material/tabs';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { UserDataService } from 'src/app/shared/services';
import { CreateServiceAccountService } from 'src/app/shared/services/create-service-account.service';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { AdminPageRoutesEnum } from '../../../config';
import { AccessKeyModalComponent } from 'src/app/shared/components';
import { UserModel } from 'src/app/shared/interfaces/user-data.interface';
import { TableActionModel, TableActionEvent } from 'src/app/shared/components/table/table.interface';
import { jest } from '@jest/globals';

import { UserPermissionsComponent } from './user-permissions.component';

describe('UserPermissionsComponent', () => {
  let component: UserPermissionsComponent;
  let fixture: ComponentFixture<UserPermissionsComponent>;
  let router: Router;
  let userDataService: UserDataService;
  let createServiceAccountService: CreateServiceAccountService;
  let dialog: MatDialog;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [UserPermissionsComponent],
      imports: [MatProgressSpinnerModule, MatTabsModule, MatIconModule, MatDialogModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({}),
            snapshot: {
              paramMap: { get: () => null },
              routeConfig: { path: 'users' },
            },
          },
        },
        {
          provide: UserDataService,
          useValue: {
            getAllUsers: jest.fn(),
            getAllServiceUsers: jest.fn(),
            deleteUser: jest.fn((body: UserModel) => of(body)),
            createServiceAccount: jest.fn(),
            getUserAccessKey: jest.fn() as jest.Mock,
          },
        },
        {
          provide: CreateServiceAccountService,
          useValue: {
            openCreateServiceAccountModal: jest.fn(() => of(undefined)),
          },
        },
        { provide: MatDialog, useValue: { open: jest.fn() } },
        { provide: Router, useValue: { navigate: jest.fn() } },
        provideHttpClient(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(UserPermissionsComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    userDataService = TestBed.inject(UserDataService);
    createServiceAccountService = TestBed.inject(CreateServiceAccountService);
    dialog = TestBed.inject(MatDialog);
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load users and service accounts on init', () => {
    jest.spyOn(userDataService, 'getAllUsers').mockReturnValue(of({ users: ['user1', 'user2'] }));
    jest.spyOn(userDataService, 'getAllServiceUsers').mockReturnValue(of({ users: ['svc1'] }));
    component.ngOnInit();
    expect(component.dataSource).toEqual([{ username: 'user1' }, { username: 'user2' }]);
    expect(component.serviceAccountsDataSource).toEqual([{ username: 'svc1' }]);
  });

  it('should handle user edit action', () => {
    const navigate = jest.spyOn(router, 'navigate');
    component.handleUserEdit({ username: 'testuser' });
    expect(navigate).toHaveBeenCalledWith([`../${AdminPageRoutesEnum.USER}/testuser`], expect.any(Object));
  });

  function getAction(action: TableActionEnum): TableActionModel {
    return { action, icon: 'icon', name: 'name' };
  }

  function getUser(username = 'user1'): UserModel {
    return { username };
  }

  it('should handle item action with EDIT', () => {
    component.handleUserEdit = jest.fn();
    component.handleItemAction({
      action: getAction(TableActionEnum.EDIT),
      item: getUser('u'),
    });
    expect(component.handleUserEdit).toHaveBeenCalledWith({ username: 'u' });
  });

  it('should not handle item action with unsupported action', () => {
    component.handleUserEdit = jest.fn();
    const unsupportedAction = {
      action: TableActionEnum.DELETE,
      icon: 'icon',
      name: 'name',
    };
    component.handleItemAction({
      action: unsupportedAction,
      item: getUser('u'),
    });
    expect(component.handleUserEdit).not.toHaveBeenCalled();
  });

  it('should handle service account action EDIT', () => {
    component.handleUserEdit = jest.fn();
    component.handleServiceAccountAction({
      action: getAction(TableActionEnum.EDIT),
      item: getUser('svc'),
    });
    expect(component.handleUserEdit).toHaveBeenCalledWith({ username: 'svc' });
  });

  it('should handle service account action DELETE', () => {
    component.handleServiceAccountDelete = jest.fn();
    component.handleServiceAccountAction({
      action: getAction(TableActionEnum.DELETE),
      item: getUser('svc'),
    });
    expect(component.handleServiceAccountDelete).toHaveBeenCalledWith({
      username: 'svc',
    });
  });

  it('should handle service account action GET_ACCESS_KEY', () => {
    component.handleAccessKey = jest.fn();
    component.handleServiceAccountAction({
      action: getAction(TableActionEnum.GET_ACCESS_KEY),
      item: getUser('svc'),
    });
    expect(component.handleAccessKey).toHaveBeenCalledWith({ username: 'svc' });
  });

  it('should not handle service account action with unsupported action', () => {
    component.handleUserEdit = jest.fn();
    const unsupportedAction = {
      action: TableActionEnum.ADD,
      icon: 'icon',
      name: 'name',
    };
    component.handleServiceAccountAction({
      action: unsupportedAction,
      item: getUser('svc'),
    });
    expect(component.handleUserEdit).not.toHaveBeenCalled();
  });

  it('should delete service account and reload data', () => {
    jest.spyOn(userDataService, 'deleteUser').mockReturnValue(of(getUser('svc')));
    jest.spyOn(userDataService, 'getAllServiceUsers').mockReturnValue(of({ users: ['svc2'] }));
    component.handleServiceAccountDelete({ username: 'svc' });
    expect(userDataService.deleteUser).toHaveBeenCalledWith({
      username: 'svc',
    });
    expect(component.isServiceAccountsLoading).toBe(false);
    expect(component.serviceAccountsDataSource).toEqual([{ username: 'svc2' }]);
  });

  it('should create service account and reload data', () => {
    const modalResult = {
      username: 'svc3',
      display_name: 'svc3',
      is_admin: false,
      is_service_account: false,
    };
    (createServiceAccountService.openCreateServiceAccountModal as jest.Mock).mockReturnValue(of(modalResult));
    jest.spyOn(userDataService, 'createServiceAccount').mockReturnValue(of(getUser('svc3')));
    jest.spyOn(userDataService, 'getAllServiceUsers').mockReturnValue(of({ users: ['svc3'] }));
    component.createServiceAccount();
    expect(createServiceAccountService.openCreateServiceAccountModal).toHaveBeenCalled();
    expect(userDataService.createServiceAccount).toHaveBeenCalledWith(modalResult);
    expect(component.serviceAccountsDataSource).toEqual([{ username: 'svc3' }]);
  });

  it('should not create service account if modal result is falsy', () => {
    (createServiceAccountService.openCreateServiceAccountModal as jest.Mock).mockReturnValue(of(undefined));
    component.createServiceAccount();
    expect(userDataService.createServiceAccount).not.toHaveBeenCalled();
  });
});
