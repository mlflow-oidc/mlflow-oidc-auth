import { provideHttpClient } from '@angular/common/http';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatIconModule } from '@angular/material/icon';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';
import { jest } from '@jest/globals';
import { PromptPermissionDetailsComponent } from './prompt-permission-details.component';
import { PromptsDataService, PermissionDataService, UserDataService, SnackBarService } from 'src/app/shared/services';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { PromptUserListModel } from 'src/app/shared/interfaces/prompts-data.interface';

describe('PromptPermissionDetailsComponent', () => {
  let component: PromptPermissionDetailsComponent;
  let fixture: ComponentFixture<PromptPermissionDetailsComponent>;
  let promptDataService: jest.Mocked<PromptsDataService>;
  let permissionDataService: jest.Mocked<PermissionDataService>;
  let userDataService: jest.Mocked<UserDataService>;
  let snackService: jest.Mocked<SnackBarService>;
  let permissionModalService: jest.Mocked<PermissionModalService>;

  beforeEach(async () => {
    promptDataService = { getUsersForPrompt: jest.fn() } as any;
    permissionDataService = {
      deletePromptPermission: jest.fn(),
      updatePromptPermission: jest.fn(),
      createPromptPermission: jest.fn(),
    } as any;
    userDataService = {
      getAllUsers: jest.fn(),
      getAllServiceUsers: jest.fn(),
    } as any;
    snackService = { openSnackBar: jest.fn() } as any;
    permissionModalService = {
      openEditPermissionsModal: jest.fn(),
      openGrantPermissionModal: jest.fn(),
    } as any;

    await TestBed.configureTestingModule({
      declarations: [PromptPermissionDetailsComponent],
      imports: [MatIconModule],
      providers: [
        provideHttpClient(),
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({ id: 'test-id' }),
            snapshot: {
              paramMap: {
                get: (key: string) => (key === 'id' ? 'test-id' : null),
              },
            },
          },
        },
        { provide: PromptsDataService, useValue: promptDataService },
        { provide: PermissionDataService, useValue: permissionDataService },
        { provide: UserDataService, useValue: userDataService },
        { provide: SnackBarService, useValue: snackService },
        { provide: PermissionModalService, useValue: permissionModalService },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(PromptPermissionDetailsComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load users on ngOnInit', () => {
    const users: PromptUserListModel[] = [{ username: 'user1', permission: PermissionEnum.READ }];
    promptDataService.getUsersForPrompt.mockReturnValue(of(users));
    component.ngOnInit();
    expect(component.promptId).toBe('test-id');
    expect(promptDataService.getUsersForPrompt).toHaveBeenCalledWith('test-id');
  });

  it('should revoke permission for user', () => {
    permissionDataService.deletePromptPermission.mockReturnValue(of({}));
    snackService.openSnackBar.mockReturnValue({} as any);
    promptDataService.getUsersForPrompt.mockReturnValue(of([{ username: 'user1', permission: PermissionEnum.READ }]));
    component.promptId = 'test-id';
    component.revokePermissionForUser({
      username: 'user1',
      permission: PermissionEnum.READ,
    });
    expect(permissionDataService.deletePromptPermission).toHaveBeenCalledWith({
      name: 'test-id',
      username: 'user1',
    });
    expect(snackService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
    expect(promptDataService.getUsersForPrompt).toHaveBeenCalledWith('test-id');
  });

  it('should edit permission for user', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.updatePromptPermission.mockReturnValue(of({}));
    snackService.openSnackBar.mockReturnValue({} as any);
    promptDataService.getUsersForPrompt.mockReturnValue(of([{ username: 'user1', permission: PermissionEnum.EDIT }]));
    component.promptId = 'test-id';
    component.editPermissionForUser({
      username: 'user1',
      permission: PermissionEnum.READ,
    });
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith(
      'test-id',
      'user1',
      PermissionEnum.READ
    );
    expect(permissionDataService.updatePromptPermission).toHaveBeenCalledWith({
      name: 'test-id',
      permission: PermissionEnum.EDIT,
      username: 'user1',
    });
    expect(snackService.openSnackBar).toHaveBeenCalledWith('Permission updated');
    expect(promptDataService.getUsersForPrompt).toHaveBeenCalledWith('test-id');
  });

  it('should handleActions REVOKE', () => {
    component.revokePermissionForUser = jest.fn();
    const event = {
      action: {
        action: TableActionEnum.REVOKE,
        icon: 'remove',
        name: 'Revoke',
      },
      item: { username: 'user1', permission: PermissionEnum.READ },
    };
    component.handleActions(event);
    expect(component.revokePermissionForUser).toHaveBeenCalledWith(event.item);
  });

  it('should handleActions EDIT', () => {
    component.editPermissionForUser = jest.fn();
    const event = {
      action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
      item: { username: 'user1', permission: PermissionEnum.READ },
    };
    component.handleActions(event);
    expect(component.editPermissionForUser).toHaveBeenCalledWith(event.item);
  });

  it('should delegate loadUsersForPrompt', () => {
    promptDataService.getUsersForPrompt.mockReturnValue(of([{ username: 'user1', permission: PermissionEnum.READ }]));
    const result$ = component.loadUsersForPrompt('test-id');
    result$.subscribe((users) => {
      expect(users).toEqual([{ username: 'user1', permission: PermissionEnum.READ }]);
    });
    expect(promptDataService.getUsersForPrompt).toHaveBeenCalledWith('test-id');
  });

  it('should add user', () => {
    userDataService.getAllUsers.mockReturnValue(of({ users: ['user1', 'user2'] }));
    permissionModalService.openGrantPermissionModal.mockReturnValue(
      of({
        entity: { id: '0user2', name: 'user2' },
        permission: PermissionEnum.EDIT,
      })
    );
    permissionDataService.createPromptPermission.mockReturnValue(of({}));
    promptDataService.getUsersForPrompt.mockReturnValue(of([{ username: 'user2', permission: PermissionEnum.EDIT }]));
    component.promptId = 'test-id';
    component.userDataSource = [{ username: 'user1', permission: PermissionEnum.READ }];
    component.addUser();
    expect(userDataService.getAllUsers).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
      EntityEnum.USER,
      [{ id: '0user2', name: 'user2' }],
      'test-id'
    );
    expect(permissionDataService.createPromptPermission).toHaveBeenCalledWith({
      name: 'test-id',
      permission: PermissionEnum.EDIT,
      username: 'user2',
    });
    expect(promptDataService.getUsersForPrompt).toHaveBeenCalledWith('test-id');
  });

  it('should add service account', () => {
    userDataService.getAllServiceUsers.mockReturnValue(of({ users: ['svc1', 'svc2'] }));
    permissionModalService.openGrantPermissionModal.mockReturnValue(
      of({
        entity: { id: '0svc2', name: 'svc2' },
        permission: PermissionEnum.READ,
      })
    );
    permissionDataService.createPromptPermission.mockReturnValue(of({}));
    promptDataService.getUsersForPrompt.mockReturnValue(of([{ username: 'svc2', permission: PermissionEnum.READ }]));
    component.promptId = 'test-id';
    component.userDataSource = [{ username: 'svc1', permission: PermissionEnum.EDIT }];
    component.addServiceAccount();
    expect(userDataService.getAllServiceUsers).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
      EntityEnum.SERVICE_ACCOUNT,
      [{ id: '0svc2', name: 'svc2' }],
      'test-id'
    );
    expect(permissionDataService.createPromptPermission).toHaveBeenCalledWith({
      name: 'test-id',
      permission: PermissionEnum.READ,
      username: 'svc2',
    });
    expect(promptDataService.getUsersForPrompt).toHaveBeenCalledWith('test-id');
  });
});
