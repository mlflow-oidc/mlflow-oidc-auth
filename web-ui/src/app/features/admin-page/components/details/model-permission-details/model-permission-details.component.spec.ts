import { provideHttpClient } from "@angular/common/http";
import { CUSTOM_ELEMENTS_SCHEMA } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatIconModule } from "@angular/material/icon";
import { MatTabsModule } from "@angular/material/tabs";
import { provideAnimations } from "@angular/platform-browser/animations";
import { ActivatedRoute } from "@angular/router";
import { of } from "rxjs";
import { jest } from '@jest/globals';
import { ModelPermissionDetailsComponent } from "./model-permission-details.component";
import { ModelsDataService, PermissionDataService, SnackBarService, UserDataService } from "src/app/shared/services";
import { PermissionModalService } from "src/app/shared/services/permission-modal.service";
import { TableActionEnum } from "src/app/shared/components/table/table.config";
import { EntityEnum } from "src/app/core/configs/core";
import { PermissionEnum } from "src/app/core/configs/permissions";

describe("ModelPermissionDetailsComponent", () => {
  let component: ModelPermissionDetailsComponent;
  let fixture: ComponentFixture<ModelPermissionDetailsComponent>;
  let modelDataService: jest.Mocked<ModelsDataService>;
  let permissionDataService: jest.Mocked<PermissionDataService>;
  let userDataService: jest.Mocked<UserDataService>;
  let permissionModalService: jest.Mocked<PermissionModalService>;
  let snackService: jest.Mocked<SnackBarService>;

  beforeEach(async () => {
    modelDataService = { getUsersForModel: jest.fn() } as any;
    permissionDataService = {
      deleteModelPermission: jest.fn(),
      updateModelPermission: jest.fn(),
      createModelPermission: jest.fn(),
    } as any;
    userDataService = {
      getAllUsers: jest.fn(),
      getAllServiceUsers: jest.fn(),
    } as any;
    permissionModalService = {
      openEditPermissionsModal: jest.fn(),
      openGrantPermissionModal: jest.fn(),
    } as any;
    snackService = { openSnackBar: jest.fn() } as any;

    await TestBed.configureTestingModule({
      declarations: [ModelPermissionDetailsComponent],
      imports: [MatTabsModule, MatIconModule],
      providers: [
        provideHttpClient(),
        provideAnimations(),
        { provide: ActivatedRoute, useValue: { params: of({ id: "test-id" }), snapshot: { paramMap: { get: () => "test-id" } } } },
        { provide: ModelsDataService, useValue: modelDataService },
        { provide: PermissionDataService, useValue: permissionDataService },
        { provide: UserDataService, useValue: userDataService },
        { provide: PermissionModalService, useValue: permissionModalService },
        { provide: SnackBarService, useValue: snackService },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(ModelPermissionDetailsComponent);
    component = fixture.componentInstance;
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it("should load users on ngOnInit", () => {
    const users = [{ username: "user1", permission: PermissionEnum.READ }];
    modelDataService.getUsersForModel.mockReturnValue(of(users));
    component.ngOnInit();
    expect(component.modelId).toBe("test-id");
    expect(modelDataService.getUsersForModel).toHaveBeenCalledWith("test-id");
  });

  it("should revoke permission for user", () => {
    permissionDataService.deleteModelPermission.mockReturnValue(of({}));
    snackService.openSnackBar.mockReturnValue({} as any);
    modelDataService.getUsersForModel.mockReturnValue(of([{ username: "user1", permission: PermissionEnum.READ }]));
    component.modelId = "test-id";
    component.revokePermissionForUser({ username: "user1", permission: PermissionEnum.READ });
    expect(permissionDataService.deleteModelPermission).toHaveBeenCalledWith({ name: "test-id", username: "user1" });
    expect(snackService.openSnackBar).toHaveBeenCalledWith("Permission revoked successfully");
    expect(modelDataService.getUsersForModel).toHaveBeenCalledWith("test-id");
  });

  it("should edit permission for user", () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.updateModelPermission.mockReturnValue(of({}) as any);
    snackService.openSnackBar.mockReturnValue({} as any);
    modelDataService.getUsersForModel.mockReturnValue(of([{ username: "user1", permission: PermissionEnum.EDIT }]));
    component.modelId = "test-id";
    component.editPermissionForUser({ username: "user1", permission: PermissionEnum.READ });
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith("test-id", "user1", PermissionEnum.READ);
    expect(permissionDataService.updateModelPermission).toHaveBeenCalledWith({ name: "test-id", permission: PermissionEnum.EDIT, username: "user1" });
    expect(snackService.openSnackBar).toHaveBeenCalledWith("Permission updated");
    expect(modelDataService.getUsersForModel).toHaveBeenCalledWith("test-id");
  });

  it("should handleActions REVOKE", () => {
    component.revokePermissionForUser = jest.fn();
    const event = {
      action: { action: TableActionEnum.REVOKE, icon: "remove", name: "Revoke" },
      item: { username: "user1", permission: PermissionEnum.READ },
    };
    component.handleActions(event);
    expect(component.revokePermissionForUser).toHaveBeenCalledWith(event.item);
  });

  it("should handleActions EDIT", () => {
    component.editPermissionForUser = jest.fn();
    const event = {
      action: { action: TableActionEnum.EDIT, icon: "edit", name: "Edit" },
      item: { username: "user1", permission: PermissionEnum.READ },
    };
    component.handleActions(event);
    expect(component.editPermissionForUser).toHaveBeenCalledWith(event.item);
  });

  it("should delegate loadUsersForModel", () => {
    modelDataService.getUsersForModel.mockReturnValue(of([{ username: "user1", permission: PermissionEnum.READ }]));
    const result$ = component.loadUsersForModel("test-id");
    result$.subscribe(users => {
      expect(users).toEqual([{ username: "user1", permission: PermissionEnum.READ }]);
    });
    expect(modelDataService.getUsersForModel).toHaveBeenCalledWith("test-id");
  });

  it("should add user", () => {
    userDataService.getAllUsers.mockReturnValue(of({ users: ["user1", "user2"] }));
    permissionModalService.openGrantPermissionModal.mockReturnValue(of({ entity: { id: "user2", name: "user2" }, permission: PermissionEnum.EDIT }));
    permissionDataService.createModelPermission.mockReturnValue(of({}));
    modelDataService.getUsersForModel.mockReturnValue(of([{ username: "user2", permission: PermissionEnum.EDIT }]));
    component.modelId = "test-id";
    component.userDataSource = [{ username: "user1", permission: PermissionEnum.READ }];
    component.addUser();
    expect(userDataService.getAllUsers).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(EntityEnum.USER, [{ id: "0user2", name: "user2" }], "test-id");
    expect(permissionDataService.createModelPermission).toHaveBeenCalledWith({ name: "test-id", permission: PermissionEnum.EDIT, username: "user2" });
    expect(modelDataService.getUsersForModel).toHaveBeenCalledWith("test-id");
  });

  it("should add service account", () => {
    userDataService.getAllServiceUsers.mockReturnValue(of({ users: ["svc1", "svc2"] }));
    permissionModalService.openGrantPermissionModal.mockReturnValue(of({ entity: { id: "svc2", name: "svc2" }, permission: PermissionEnum.READ }));
    permissionDataService.createModelPermission.mockReturnValue(of({}));
    modelDataService.getUsersForModel.mockReturnValue(of([{ username: "svc2", permission: PermissionEnum.READ }]));
    component.modelId = "test-id";
    component.userDataSource = [{ username: "svc1", permission: PermissionEnum.EDIT }];
    component.addServiceAccount();
    expect(userDataService.getAllServiceUsers).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(EntityEnum.SERVICE_ACCOUNT, [{ id: "0svc2", name: "svc2" }], "test-id");
    expect(permissionDataService.createModelPermission).toHaveBeenCalledWith({ name: "test-id", permission: PermissionEnum.READ, username: "svc2" });
    expect(modelDataService.getUsersForModel).toHaveBeenCalledWith("test-id");
  });
});
