import { provideHttpClient } from "@angular/common/http";
import { CUSTOM_ELEMENTS_SCHEMA } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatIconModule } from "@angular/material/icon";
import { ActivatedRoute } from "@angular/router";
import { RouterTestingModule } from "@angular/router/testing";
import { ExperimentsDataService, PermissionDataService, SnackBarService, UserDataService } from "src/app/shared/services";
import { PermissionModalService } from "src/app/shared/services/permission-modal.service";
import { TableActionEnum } from "src/app/shared/components/table/table.config";
import { Observable, of } from "rxjs";
import { PermissionEnum } from "src/app/core/configs/permissions";
import { jest } from '@jest/globals';
import { ExperimentPermissionDetailsComponent } from "./experiment-permission-details.component";
import { UserPermissionModel } from "src/app/shared/interfaces/experiments-data.interface";
import { EntityEnum } from "src/app/core/configs/core";

describe("ExperimentPermissionDetailsComponent", () => {
  let component: ExperimentPermissionDetailsComponent;
  let fixture: ComponentFixture<ExperimentPermissionDetailsComponent>;
  let experimentDataService: jest.Mocked<ExperimentsDataService>;
  let permissionDataService: jest.Mocked<PermissionDataService>;
  let userDataService: jest.Mocked<UserDataService>;
  let permissionModalService: jest.Mocked<PermissionModalService>;
  let snackBarService: jest.Mocked<SnackBarService>;

  beforeEach(async () => {
    experimentDataService = {
      getUsersForExperiment: jest.fn()
    } as any;
    permissionDataService = {
      updateExperimentPermission: jest.fn(),
      deleteExperimentPermission: jest.fn(),
      createExperimentPermission: jest.fn()
    } as any;
    userDataService = {
      getAllUsers: jest.fn(),
      getAllServiceUsers: jest.fn()
    } as any;
    permissionModalService = {
      openEditPermissionsModal: jest.fn(),
      openGrantPermissionModal: jest.fn(),
    } as any;
    snackBarService = {
      openSnackBar: jest.fn()
    } as any;

    await TestBed.configureTestingModule({
      imports: [RouterTestingModule, MatIconModule],
      declarations: [ExperimentPermissionDetailsComponent],
      providers: [
        provideHttpClient(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: (key: string) => (key === "id" ? "test-id" : null) } }, params: of({ id: "test-id" }) } },
        { provide: ExperimentsDataService, useValue: experimentDataService },
        { provide: PermissionDataService, useValue: permissionDataService },
        { provide: UserDataService, useValue: userDataService },
        { provide: PermissionModalService, useValue: permissionModalService },
        { provide: SnackBarService, useValue: snackBarService },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(ExperimentPermissionDetailsComponent);
    component = fixture.componentInstance;
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it('should load users on ngOnInit', () => {
    const users = [{ username: 'user1', permission: PermissionEnum.READ }];
    experimentDataService.getUsersForExperiment.mockReturnValue(of(users));
    component.ngOnInit();
    expect(component.experimentId).toBe('test-id');
    expect(experimentDataService.getUsersForExperiment).toHaveBeenCalledWith('test-id');
  });

  it('should handle user edit', () => {
    const event = { username: 'user1', permission: PermissionEnum.READ };
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.updateExperimentPermission.mockReturnValue(of('EDIT'));
    snackBarService.openSnackBar.mockReturnValue({} as any); // mock MatSnackBarRef
    experimentDataService.getUsersForExperiment.mockReturnValue(of([{ username: 'user1', permission: PermissionEnum.EDIT }]));
    component.experimentId = 'test-id';
    component.handleUserEdit(event);
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith('test-id', 'user1', PermissionEnum.READ);
    expect(permissionDataService.updateExperimentPermission).toHaveBeenCalledWith({ experiment_id: 'test-id', permission: PermissionEnum.EDIT, username: 'user1' });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permissions updated successfully');
  });

  it('should handleActions EDIT', () => {
    component.handleUserEdit = jest.fn();
    const event = {
      action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
      item: { username: 'user1', permission: PermissionEnum.READ }
    };
    component.handleActions(event);
    expect(component.handleUserEdit).toHaveBeenCalledWith(event.item);
  });

  it('should handleActions REVOKE', () => {
    component.revokePermissionForUser = jest.fn();
    const event = {
      action: { action: TableActionEnum.REVOKE, icon: 'remove', name: 'Revoke' },
      item: { username: 'user1', permission: PermissionEnum.READ }
    };
    component.handleActions(event);
    expect(component.revokePermissionForUser).toHaveBeenCalledWith(event.item);
  });

  it('should revoke permission for user', () => {
    permissionDataService.deleteExperimentPermission.mockReturnValue(of({}));
    snackBarService.openSnackBar.mockReturnValue({} as any); // mock MatSnackBarRef
    component.loadUsersForExperiment = jest.fn().mockReturnValue(of([{ username: 'user1', permission: PermissionEnum.READ } as UserPermissionModel])) as unknown as (experimentId: string) => Observable<UserPermissionModel[]>;
    component.experimentId = 'test-id';
    component.revokePermissionForUser({ username: 'user1', permission: PermissionEnum.READ });
    expect(permissionDataService.deleteExperimentPermission).toHaveBeenCalledWith({ experiment_id: 'test-id', username: 'user1' });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
    expect(component.loadUsersForExperiment).toHaveBeenCalledWith('test-id');
  });

  it('should add user', () => {
    userDataService.getAllUsers.mockReturnValue(of({ users: ['user1', 'user2'] }));
    permissionModalService.openGrantPermissionModal.mockReturnValue(of({ entity: { id: '0-user2', name: 'user2' }, permission: PermissionEnum.EDIT }));
    permissionDataService.createExperimentPermission.mockReturnValue(of('EDIT'));
    component.loadUsersForExperiment = jest.fn().mockReturnValue(of([{ username: 'user2', permission: PermissionEnum.EDIT } as UserPermissionModel])) as unknown as (experimentId: string) => Observable<UserPermissionModel[]>;
    component.experimentId = 'test-id';
    component.userDataSource = [{ username: 'user1', permission: PermissionEnum.READ }];
    component.addUser();
    expect(userDataService.getAllUsers).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
      EntityEnum.USER,
      [{ id: '0-user2', name: 'user2' }],
      'test-id'
    );
    expect(permissionDataService.createExperimentPermission).toHaveBeenCalledWith({ experiment_id: 'test-id', permission: PermissionEnum.EDIT, username: 'user2' });
    expect(component.loadUsersForExperiment).toHaveBeenCalledWith('test-id');
  });

  it('should add service account', () => {
    userDataService.getAllServiceUsers.mockReturnValue(of({ users: ['svc1', 'svc2'] }));
    permissionModalService.openGrantPermissionModal.mockReturnValue(of({ entity: { id: '0-svc2', name: 'svc2' }, permission: PermissionEnum.READ }));
    permissionDataService.createExperimentPermission.mockReturnValue(of('READ'));
    component.loadUsersForExperiment = jest.fn().mockReturnValue(of([{ username: 'svc2', permission: PermissionEnum.READ } as UserPermissionModel])) as unknown as (experimentId: string) => Observable<UserPermissionModel[]>;
    component.experimentId = 'test-id';
    component.userDataSource = [{ username: 'svc1', permission: PermissionEnum.EDIT }];
    component.addServiceAccount();
    expect(userDataService.getAllServiceUsers).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
      EntityEnum.SERVICE_ACCOUNT,
      [{ id: '0-svc2', name: 'svc2' }],
      'test-id'
    );
    expect(permissionDataService.createExperimentPermission).toHaveBeenCalledWith({ experiment_id: 'test-id', permission: PermissionEnum.READ, username: 'svc2' });
    expect(component.loadUsersForExperiment).toHaveBeenCalledWith('test-id');
  });

  it('should delegate loadUsersForExperiment', () => {
    experimentDataService.getUsersForExperiment.mockReturnValue(of([{ username: 'user1', permission: PermissionEnum.READ }]));
    const result$ = component.loadUsersForExperiment('test-id');
    result$.subscribe(users => {
      expect(users).toEqual([{ username: 'user1', permission: PermissionEnum.READ }]);
    });
    expect(experimentDataService.getUsersForExperiment).toHaveBeenCalledWith('test-id');
  });
});
