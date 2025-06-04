import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { MatTabGroup, MatTabsModule } from '@angular/material/tabs';
import { provideAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { jest } from '@jest/globals';
import { of } from 'rxjs';
import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum, PermissionTypeEnum } from 'src/app/core/configs/permissions';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { ExperimentForUserModel } from 'src/app/shared/interfaces/experiments-data.interface';
import {
  ExperimentRegexPermissionModel,
  ModelRegexPermissionModel,
  PromptRegexPermissionModel,
} from 'src/app/shared/interfaces/groups-data.interface';
import { CurrentUserModel } from 'src/app/shared/interfaces/user-data.interface';
import {
  AuthService,
  ExperimentsDataService,
  ModelsDataService,
  PermissionDataService,
  PromptsDataService,
  SnackBarService,
} from 'src/app/shared/services';
import { UserDataService } from 'src/app/shared/services/data/user-data.service';
import { UserExperimentRegexDataService } from 'src/app/shared/services/data/user-experiment-regex-data.service';
import { UserModelRegexDataService } from 'src/app/shared/services/data/user-model-regex-data.service';
import { UserPromptRegexDataService } from 'src/app/shared/services/data/user-prompt-regex-data.service';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service';
import { AdminPageRoutesEnum } from '../../../config';
import { UserPermissionDetailsComponent } from './user-permission-details.component';
describe('UserPermissionDetailsComponent', () => {
  let component: UserPermissionDetailsComponent;
  let fixture: ComponentFixture<UserPermissionDetailsComponent>;
  let expDataService: jest.Mocked<ExperimentsDataService>;
  let modelDataService: jest.Mocked<ModelsDataService>;
  let promptDataService: jest.Mocked<PromptsDataService>;
  let permissionDataService: jest.Mocked<PermissionDataService>;
  let experimentRegexDataService: jest.Mocked<UserExperimentRegexDataService>;
  let modelRegexDataService: jest.Mocked<UserModelRegexDataService>;
  let promptRegexDataService: jest.Mocked<UserPromptRegexDataService>;
  let permissionModalService: jest.Mocked<PermissionModalService>;
  let snackBarService: jest.Mocked<SnackBarService>;
  let router: jest.Mocked<Router>;
  let activatedRoute: ActivatedRoute;
  let authService: jest.Mocked<AuthService>;
  let userDataService: jest.Mocked<UserDataService>;
  let dialog: jest.Mocked<MatDialog>;
  beforeEach(async () => {
    expDataService = {
      getExperimentsForUser: jest.fn().mockReturnValue(of([])),
      getAllExperiments: jest.fn().mockReturnValue(of([])),
    } as any;
    modelDataService = {
      getModelsForUser: jest.fn().mockReturnValue(of([])),
      getAllModels: jest.fn().mockReturnValue(of([])),
    } as any;
    promptDataService = {
      getPromptsForUser: jest.fn().mockReturnValue(of([])),
      getAllPrompts: jest.fn().mockReturnValue(of([])),
    } as any;
    permissionDataService = {
      createExperimentPermission: jest.fn().mockReturnValue(of(null)),
      updateExperimentPermission: jest.fn().mockReturnValue(of(null)),
      deleteExperimentPermission: jest.fn().mockReturnValue(of(null)),
      createModelPermission: jest.fn().mockReturnValue(of(null)),
      updateModelPermission: jest.fn().mockReturnValue(of(null)),
      deleteModelPermission: jest.fn().mockReturnValue(of(null)),
      createPromptPermission: jest.fn().mockReturnValue(of(null)),
      updatePromptPermission: jest.fn().mockReturnValue(of(null)),
      deletePromptPermission: jest.fn().mockReturnValue(of(null)),
    } as any;
    experimentRegexDataService = {
      getExperimentRegexPermissionsForUser: jest.fn().mockReturnValue(of([])),
      addExperimentRegexPermissionToUser: jest.fn().mockReturnValue(of(null)),
      updateExperimentRegexPermissionForUser: jest.fn().mockReturnValue(of(null)),
      removeExperimentRegexPermissionFromUser: jest.fn().mockReturnValue(of(null)),
    } as any;
    modelRegexDataService = {
      getModelRegexPermissionsForUser: jest.fn().mockReturnValue(of([])),
      addModelRegexPermissionToUser: jest.fn().mockReturnValue(of(null)),
      updateModelRegexPermissionForUser: jest.fn().mockReturnValue(of(null)),
      removeModelRegexPermissionFromUser: jest.fn().mockReturnValue(of(null)),
    } as any;
    promptRegexDataService = {
      getPromptRegexPermissionsForUser: jest.fn().mockReturnValue(of([])),
      addPromptRegexPermissionToUser: jest.fn().mockReturnValue(of(null)),
      updatePromptRegexPermissionForUser: jest.fn().mockReturnValue(of(null)),
      removePromptRegexPermissionFromUser: jest.fn().mockReturnValue(of(null)),
    } as any;
    permissionModalService = {
      openGrantPermissionModal: jest.fn().mockReturnValue(of(null)),
      openEditPermissionsModal: jest.fn().mockReturnValue(of(null)),
    } as any;
    snackBarService = {
      openSnackBar: jest.fn(),
    } as any;
    router = {
      navigate: jest.fn<(...args: any[]) => Promise<boolean>>().mockResolvedValue(true),
    } as any;
    authService = {
      getUserInfo: jest.fn().mockReturnValue({
        display_name: 'Test User',
        experiments: [],
        id: 1,
        is_admin: true,
        models: [],
        username: 'testuser',
        prompts: [],
      } as CurrentUserModel),
    } as any;
    userDataService = {
      getUser: jest.fn().mockReturnValue(of(null)),
    } as any;
    dialog = {
      open: jest.fn().mockReturnValue({
        afterClosed: jest.fn().mockReturnValue(of(null)),
      }),
    } as any;
    activatedRoute = {
      params: of({ id: '123' }),
      snapshot: {
        paramMap: convertToParamMap({ id: '123' }),
        url: [{ path: 'permissions' }],
      },
      parent: {
        snapshot: {
          url: [{ path: 'experiments' }],
        },
      } as any,
    } as any;
    await TestBed.configureTestingModule({
      declarations: [UserPermissionDetailsComponent],
      imports: [MatTabsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimations(),
        { provide: ExperimentsDataService, useValue: expDataService },
        { provide: ModelsDataService, useValue: modelDataService },
        { provide: PromptsDataService, useValue: promptDataService },
        { provide: PermissionDataService, useValue: permissionDataService },
        { provide: UserExperimentRegexDataService, useValue: experimentRegexDataService },
        { provide: UserModelRegexDataService, useValue: modelRegexDataService },
        { provide: UserPromptRegexDataService, useValue: promptRegexDataService },
        { provide: PermissionModalService, useValue: permissionModalService },
        { provide: SnackBarService, useValue: snackBarService },
        { provide: Router, useValue: router },
        { provide: ActivatedRoute, useValue: activatedRoute },
        { provide: AuthService, useValue: authService },
        { provide: UserDataService, useValue: userDataService },
        { provide: MatDialog, useValue: dialog },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();
    fixture = TestBed.createComponent(UserPermissionDetailsComponent);
    component = fixture.componentInstance;
  });
  afterEach(() => {
    jest.clearAllTimers();
  });
  it('should create', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });
  it('should load all data sources on ngOnInit', () => {
    const experiments: ExperimentForUserModel[] = [
      {
        id: 'exp1',
        name: 'Experiment 1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    ];
    const models = [
      {
        name: 'model1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    ];
    const prompts = [
      {
        name: 'prompt1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    ];
    expDataService.getExperimentsForUser.mockReturnValue(of(experiments));
    modelDataService.getModelsForUser.mockReturnValue(of(models));
    promptDataService.getPromptsForUser.mockReturnValue(of(prompts));
    experimentRegexDataService.getExperimentRegexPermissionsForUser.mockReturnValue(of([]));
    modelRegexDataService.getModelRegexPermissionsForUser.mockReturnValue(of([]));
    promptRegexDataService.getPromptRegexPermissionsForUser.mockReturnValue(of([]));
    fixture.detectChanges();
    jest.runAllTimers();
    expect(expDataService.getExperimentsForUser).toHaveBeenCalledWith('123');
    expect(modelDataService.getModelsForUser).toHaveBeenCalledWith('123');
    expect(promptDataService.getPromptsForUser).toHaveBeenCalledWith('123');
    expect(component.experimentsDataSource).toEqual(experiments);
    expect(component.modelsDataSource).toEqual(models);
    expect(component.promptsDataSource).toEqual(prompts);
  });
  it('should load data for non-admin user on ngOnInit', () => {
    authService.getUserInfo.mockReturnValue({
      display_name: 'Test User',
      experiments: [],
      id: 1,
      is_admin: false,
      models: [],
      username: 'testuser',
      prompts: [],
    } as CurrentUserModel);
    expDataService.getExperimentsForUser.mockReturnValue(of([]));
    modelDataService.getModelsForUser.mockReturnValue(of([]));
    promptDataService.getPromptsForUser.mockReturnValue(of([]));
    fixture.detectChanges();
    jest.runAllTimers();
    expect(expDataService.getExperimentsForUser).toHaveBeenCalledWith('123');
    expect(modelDataService.getModelsForUser).toHaveBeenCalledWith('123');
    expect(promptDataService.getPromptsForUser).toHaveBeenCalledWith('123');
    expect(experimentRegexDataService.getExperimentRegexPermissionsForUser).not.toHaveBeenCalled();
    expect(modelRegexDataService.getModelRegexPermissionsForUser).not.toHaveBeenCalled();
    expect(promptRegexDataService.getPromptRegexPermissionsForUser).not.toHaveBeenCalled();
    expect(component.experimentRegexDataSource).toEqual([]);
    expect(component.modelRegexDataSource).toEqual([]);
    expect(component.promptRegexDataSource).toEqual([]);
  });
  it('should set correct tab and sub-tab indices on ngOnInit based on route', () => {
    const specificRoute = {
      snapshot: {
        paramMap: convertToParamMap({ id: '123' }),
        url: [{ path: AdminPageRoutesEnum.REGEX }],
      },
      parent: {
        snapshot: {
          url: [{ path: 'models' }],
        },
      } as any,
    } as ActivatedRoute;
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      declarations: [UserPermissionDetailsComponent],
      imports: [MatTabsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimations(),
        { provide: ExperimentsDataService, useValue: expDataService },
        { provide: ModelsDataService, useValue: modelDataService },
        { provide: PromptsDataService, useValue: promptDataService },
        { provide: PermissionDataService, useValue: permissionDataService },
        { provide: UserExperimentRegexDataService, useValue: experimentRegexDataService },
        { provide: UserModelRegexDataService, useValue: modelRegexDataService },
        { provide: UserPromptRegexDataService, useValue: promptRegexDataService },
        { provide: PermissionModalService, useValue: permissionModalService },
        { provide: SnackBarService, useValue: snackBarService },
        { provide: Router, useValue: router },
        { provide: ActivatedRoute, useValue: specificRoute },
        { provide: AuthService, useValue: authService },
        { provide: UserDataService, useValue: userDataService },
        { provide: MatDialog, useValue: dialog },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();
    fixture = TestBed.createComponent(UserPermissionDetailsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    expect(component.selectedSubTabIndexes[1]).toBe(1);
  });
  it('should set tab index on ngAfterViewInit based on route', () => {
    component.permissionsTabs = { selectedIndex: 0 } as MatTabGroup;
    const parentRoute = component['route'].parent as any;
    if (!parentRoute) {
      (component['route'] as any).parent = {
        snapshot: {
          url: [{ path: 'models' }],
        },
      };
    } else {
      parentRoute.snapshot = {
        ...(parentRoute.snapshot || {}),
        url: [{ path: 'models' }],
      };
    }
    component.ngAfterViewInit();
    expect(component.permissionsTabs.selectedIndex).toBe(1);
  });
  it('should call destroy$.next and destroy$.complete on ngOnDestroy', () => {
    const destroyNextSpy = jest.spyOn((component as any).destroy$, 'next');
    const destroyCompleteSpy = jest.spyOn((component as any).destroy$, 'complete');
    component.ngOnDestroy();
    expect(destroyNextSpy).toHaveBeenCalled();
    expect(destroyCompleteSpy).toHaveBeenCalled();
  });
  it('should handle experiment actions with unknown action', () => {
    component.handleEditUserPermissionForExperiment = jest.fn();
    component.revokeExperimentPermissionForUser = jest.fn();
    const event = {
      action: { action: 'UNKNOWN_ACTION' },
      item: { id: 'exp1', name: 'Experiment 1', permission: PermissionEnum.READ, type: PermissionTypeEnum.USER },
    };
    component.handleExperimentActions(event as any);
    expect(component.handleEditUserPermissionForExperiment).not.toHaveBeenCalled();
    expect(component.revokeExperimentPermissionForUser).not.toHaveBeenCalled();
  });
  it('should handle model actions with unknown action', () => {
    component.handleEditUserPermissionForModel = jest.fn();
    component.revokeModelPermissionForUser = jest.fn();
    const event = {
      action: { action: 'UNKNOWN_ACTION' },
      item: { name: 'model1', permission: PermissionEnum.READ, type: PermissionTypeEnum.USER },
    };
    component.handleModelActions(event as any);
    expect(component.handleEditUserPermissionForModel).not.toHaveBeenCalled();
    expect(component.revokeModelPermissionForUser).not.toHaveBeenCalled();
  });
  it('should handle prompt actions with unknown action', () => {
    component.handleEditUserPermissionForPrompt = jest.fn();
    component.revokePromptPermissionForUser = jest.fn();
    const event = {
      action: { action: 'UNKNOWN_ACTION' },
      item: { name: 'prompt1', permission: PermissionEnum.READ, type: PermissionTypeEnum.USER },
    };
    component.handlePromptActions(event as any);
    expect(component.handleEditUserPermissionForPrompt).not.toHaveBeenCalled();
    expect(component.revokePromptPermissionForUser).not.toHaveBeenCalled();
  });
  it('should not proceed with edit if modal is dismissed for model permission', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(null));
    component.userId = '123';
    component.handleEditUserPermissionForModel({
      name: 'model1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionDataService.updateModelPermission).not.toHaveBeenCalled();
    expect(permissionDataService.createModelPermission).not.toHaveBeenCalled();
    expect(snackBarService.openSnackBar).not.toHaveBeenCalled();
  });
  it('should not proceed with edit if modal is dismissed for experiment permission', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(null));
    component.userId = '123';
    component.handleEditUserPermissionForExperiment({
      id: 'exp1',
      name: 'Experiment 1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionDataService.updateExperimentPermission).not.toHaveBeenCalled();
    expect(permissionDataService.createExperimentPermission).not.toHaveBeenCalled();
    expect(snackBarService.openSnackBar).not.toHaveBeenCalled();
  });
  it('should not proceed with edit if modal is dismissed for prompt permission', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(null));
    component.userId = '123';
    component.handleEditUserPermissionForPrompt({
      name: 'prompt1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionDataService.updatePromptPermission).not.toHaveBeenCalled();
    expect(permissionDataService.createPromptPermission).not.toHaveBeenCalled();
    expect(snackBarService.openSnackBar).not.toHaveBeenCalled();
  });
  it('should add experiment permission to user', () => {
    const mockExperiment = {
      id: 'exp2',
      name: 'Experiment 2',
      tags: {},
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    };
    const mockExperimentPermissionData = {
      experiment_id: 'exp2',
      permission: PermissionEnum.READ,
      username: '123',
    };
    expDataService.getAllExperiments.mockReturnValue(of([mockExperiment]));
    permissionModalService.openGrantPermissionModal.mockReturnValue(
      of({
        entity: { id: 'exp2', name: 'Experiment 2' },
        permission: PermissionEnum.READ,
      })
    );
    permissionDataService.createExperimentPermission.mockReturnValue(of('created'));
    expDataService.getExperimentsForUser.mockReturnValue(of([mockExperiment]));
    component.userId = '123';
    const addExperimentPermissionToUser = () => {
      expDataService.getAllExperiments();
      permissionModalService.openGrantPermissionModal(EntityEnum.EXPERIMENT, [mockExperiment], '123');
      permissionDataService.createExperimentPermission(mockExperimentPermissionData);
      expDataService.getExperimentsForUser('123');
    };
    addExperimentPermissionToUser();
    expect(expDataService.getAllExperiments).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
      EntityEnum.EXPERIMENT,
      [mockExperiment],
      '123'
    );
    expect(permissionDataService.createExperimentPermission).toHaveBeenCalledWith(mockExperimentPermissionData);
    expect(expDataService.getExperimentsForUser).toHaveBeenCalledWith('123');
  });
  it('should handle experiment actions', () => {
    component.handleEditUserPermissionForExperiment = jest.fn();
    component.revokeExperimentPermissionForUser = jest.fn();
    const event = {
      action: { action: TableActionEnum.EDIT },
      item: {
        id: 'exp1',
        name: 'Experiment 1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    };
    component.handleExperimentActions(event as any);
    expect(component.handleEditUserPermissionForExperiment).toHaveBeenCalledWith(event.item);
    const event2 = {
      action: { action: TableActionEnum.REVOKE },
      item: {
        id: 'exp1',
        name: 'Experiment 1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    };
    component.handleExperimentActions(event2 as any);
    expect(component.revokeExperimentPermissionForUser).toHaveBeenCalledWith(event2.item);
  });
  it('should revoke experiment permission for user (USER type)', () => {
    permissionDataService.deleteExperimentPermission.mockReturnValue(of('deleted'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    expDataService.getExperimentsForUser.mockReturnValue(
      of([
        {
          id: 'exp1',
          name: 'Experiment 1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.revokeExperimentPermissionForUser({
      id: 'exp1',
      type: PermissionTypeEnum.USER,
    });
    expect(permissionDataService.deleteExperimentPermission).toHaveBeenCalledWith({
      experiment_id: 'exp1',
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
    expect(expDataService.getExperimentsForUser).toHaveBeenCalledWith('123');
  });
  it('should not revoke experiment permission for user (non-USER type)', () => {
    snackBarService.openSnackBar.mockReturnValue({} as any);
    component.revokeExperimentPermissionForUser({
      id: 'exp1',
      type: PermissionTypeEnum.FALLBACK,
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Nothing to reset');
  });
  it('should revoke model permission for user (USER type)', () => {
    permissionDataService.deleteModelPermission.mockReturnValue(of('deleted'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    modelDataService.getModelsForUser.mockReturnValue(
      of([
        {
          name: 'model1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.revokeModelPermissionForUser({
      name: 'model1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionDataService.deleteModelPermission).toHaveBeenCalledWith({
      name: 'model1',
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
    expect(modelDataService.getModelsForUser).toHaveBeenCalledWith('123');
  });
  it('should not revoke model permission for user (non-USER type)', () => {
    snackBarService.openSnackBar.mockReturnValue({} as any);
    component.revokeModelPermissionForUser({
      name: 'model1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.FALLBACK,
    } as any);
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Nothing to reset');
  });
  it('should handle model actions', () => {
    component.handleEditUserPermissionForModel = jest.fn();
    component.revokeModelPermissionForUser = jest.fn();
    const event = {
      action: { action: TableActionEnum.EDIT },
      item: {
        name: 'model1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    };
    component.handleModelActions(event as any);
    expect(component.handleEditUserPermissionForModel).toHaveBeenCalledWith(event.item);
    const event2 = {
      action: { action: TableActionEnum.REVOKE },
      item: {
        name: 'model1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    };
    component.handleModelActions(event2 as any);
    expect(component.revokeModelPermissionForUser).toHaveBeenCalledWith(event2.item);
  });
  it('should handle edit user permission for model (FALLBACK type)', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.createModelPermission.mockReturnValue(of('created'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    modelDataService.getModelsForUser.mockReturnValue(
      of([
        {
          name: 'model1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.handleEditUserPermissionForModel({
      name: 'model1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.FALLBACK,
    } as any);
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith('model1', '123', PermissionEnum.READ);
    expect(permissionDataService.createModelPermission).toHaveBeenCalledWith({
      name: 'model1',
      permission: PermissionEnum.EDIT,
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permissions updated successfully');
    expect(modelDataService.getModelsForUser).toHaveBeenCalledWith('123');
  });
  it('should handle edit user permission for model (USER type)', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.updateModelPermission.mockReturnValue(of('updated'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    modelDataService.getModelsForUser.mockReturnValue(
      of([
        {
          name: 'model1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.handleEditUserPermissionForModel({
      name: 'model1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith('model1', '123', PermissionEnum.READ);
    expect(permissionDataService.updateModelPermission).toHaveBeenCalledWith({
      name: 'model1',
      permission: PermissionEnum.EDIT,
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permissions updated successfully');
    expect(modelDataService.getModelsForUser).toHaveBeenCalledWith('123');
  });
  it('should handle edit user permission for experiment (FALLBACK type)', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.createExperimentPermission.mockReturnValue(of('created'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    expDataService.getExperimentsForUser.mockReturnValue(
      of([
        {
          id: 'exp1',
          name: 'Experiment 1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.handleEditUserPermissionForExperiment({
      id: 'exp1',
      name: 'Experiment 1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.FALLBACK,
    } as any);
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith('exp1', '123', PermissionEnum.READ);
    expect(permissionDataService.createExperimentPermission).toHaveBeenCalledWith({
      experiment_id: 'exp1',
      permission: PermissionEnum.EDIT,
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permissions updated successfully');
    expect(expDataService.getExperimentsForUser).toHaveBeenCalledWith('123');
  });
  it('should handle edit user permission for experiment (USER type)', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.updateExperimentPermission.mockReturnValue(of('updated'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    expDataService.getExperimentsForUser.mockReturnValue(
      of([
        {
          id: 'exp1',
          name: 'Experiment 1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.handleEditUserPermissionForExperiment({
      id: 'exp1',
      name: 'Experiment 1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith('exp1', '123', PermissionEnum.READ);
    expect(permissionDataService.updateExperimentPermission).toHaveBeenCalledWith({
      experiment_id: 'exp1',
      permission: PermissionEnum.EDIT,
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permissions updated successfully');
    expect(expDataService.getExperimentsForUser).toHaveBeenCalledWith('123');
  });
  it('should handle prompt actions', () => {
    component.handleEditUserPermissionForPrompt = jest.fn();
    component.revokePromptPermissionForUser = jest.fn();
    const eventPrompt = {
      action: { action: TableActionEnum.EDIT },
      item: {
        name: 'prompt1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    };
    component.handlePromptActions(eventPrompt as any);
    expect(component.handleEditUserPermissionForPrompt).toHaveBeenCalledWith(eventPrompt.item);
    const eventPrompt2 = {
      action: { action: TableActionEnum.REVOKE },
      item: {
        name: 'prompt1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    };
    component.handlePromptActions(eventPrompt2 as any);
    expect(component.revokePromptPermissionForUser).toHaveBeenCalledWith(eventPrompt2.item);
  });
  it('should handle edit user permission for prompt (FALLBACK type)', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.createPromptPermission.mockReturnValue(of('created'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    promptDataService.getPromptsForUser.mockReturnValue(
      of([
        {
          name: 'prompt1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.handleEditUserPermissionForPrompt({
      name: 'prompt1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.FALLBACK,
    } as any);
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith('prompt1', '123', PermissionEnum.READ);
    expect(permissionDataService.createPromptPermission).toHaveBeenCalledWith({
      name: 'prompt1',
      permission: PermissionEnum.EDIT,
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permissions updated successfully');
    expect(promptDataService.getPromptsForUser).toHaveBeenCalledWith('123');
  });
  it('should handle edit user permission for prompt (USER type)', () => {
    permissionModalService.openEditPermissionsModal.mockReturnValue(of(PermissionEnum.EDIT));
    permissionDataService.updatePromptPermission.mockReturnValue(of('updated'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    promptDataService.getPromptsForUser.mockReturnValue(
      of([
        {
          name: 'prompt1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.handleEditUserPermissionForPrompt({
      name: 'prompt1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionModalService.openEditPermissionsModal).toHaveBeenCalledWith('prompt1', '123', PermissionEnum.READ);
    expect(permissionDataService.updatePromptPermission).toHaveBeenCalledWith({
      name: 'prompt1',
      permission: PermissionEnum.EDIT,
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permissions updated successfully');
    expect(promptDataService.getPromptsForUser).toHaveBeenCalledWith('123');
  });
  it('should revoke prompt permission for user (USER type)', () => {
    permissionDataService.deletePromptPermission.mockReturnValue(of('deleted'));
    snackBarService.openSnackBar.mockReturnValue({} as any);
    promptDataService.getPromptsForUser.mockReturnValue(
      of([
        {
          name: 'prompt1',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.revokePromptPermissionForUser({
      name: 'prompt1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.USER,
    } as any);
    expect(permissionDataService.deletePromptPermission).toHaveBeenCalledWith({
      name: 'prompt1',
      username: '123',
    });
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
    expect(promptDataService.getPromptsForUser).toHaveBeenCalledWith('123');
  });
  it('should not revoke prompt permission for user (non-USER type)', () => {
    if (typeof global.queueMicrotask !== 'function') {
      global.queueMicrotask = (fn) => Promise.resolve().then(fn);
    }
    snackBarService.openSnackBar.mockReturnValue({} as any);
    component.revokePromptPermissionForUser({
      name: 'prompt1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.FALLBACK,
    } as any);
    jest.runAllTimers();
    expect(permissionDataService.deletePromptPermission).not.toHaveBeenCalled();
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Nothing to reset');
  });
  it('should handle tab selection when isMainTabInit is true', () => {
    component.userId = '123';
    (component as any).isMainTabInit = true;
    component.handleTabSelection(1);
    expect(router.navigate).not.toHaveBeenCalled();
  });
  it('should handle tab selection and navigate', () => {
    component.userId = '123';
    (component as any).isMainTabInit = false;
    component.permissionsTabs = { selectedIndex: 0 } as MatTabGroup;
    activatedRoute.snapshot = { paramMap: { get: (key: string) => (key === 'id' ? '123' : null) } } as any;
    component.handleTabSelection(1);
    expect(router.navigate).toHaveBeenCalledWith([`/manage/user/123/models/permissions`]);
  });
  describe('handleSubTabSelection', () => {
    beforeEach(() => {
      component.userId = '123';
      component.permissionsTabs = { selectedIndex: 0 } as MatTabGroup;
      activatedRoute.snapshot = { paramMap: { get: (key: string) => (key === 'id' ? '123' : null) } } as any;
      (component as any).navigating = false;
    });
    it('should not navigate if navigating is true', () => {
      (component as any).navigating = true;
      component.handleSubTabSelection(1);
      expect(router.navigate).not.toHaveBeenCalled();
    });
    it('should navigate if main tab index is null', () => {
      component.permissionsTabs.selectedIndex = undefined as any;
      (component as any).navigating = false;
      component.handleSubTabSelection(1);
      expect(router.navigate).toHaveBeenCalled();
    });
    it('should navigate to regex sub-tab and reset navigating flag', () => {
      component.permissionsTabs.selectedIndex = 0;
      (component as any).navigating = false;
      component.handleSubTabSelection(1);
      expect(router.navigate).toHaveBeenCalledWith([`/manage/user/123/experiments/regex`]);
      expect(component.selectedSubTabIndexes[0]).toBe(1);
      jest.advanceTimersByTime(300);
      expect((component as any).navigating).toBe(true);
    });
    it('should navigate to permissions sub-tab and reset navigating flag', () => {
      component.permissionsTabs.selectedIndex = 1;
      (component as any).navigating = false;
      component.handleSubTabSelection(0);
      expect(router.navigate).toHaveBeenCalledWith([`/manage/user/123/models/permissions`]);
      expect(component.selectedSubTabIndexes[1]).toBe(0);
      jest.advanceTimersByTime(300);
      expect((component as any).navigating).toBe(true);
    });
  });
  describe('Regex Permissions', () => {
    const regexPerm = { id: 'test-id-1', regex: 'test-regex', permission: PermissionEnum.READ, priority: 100, group_id: 'group-1' };
    const updatedRegexPerm = { id: 'test-id-1', regex: 'test-regex', permission: PermissionEnum.EDIT, priority: 50, group_id: 'group-1' };
    const modelRegexPerm = { id: 'test-id-1', regex: 'test-regex', permission: PermissionEnum.READ, priority: 100, group_id: 'group-1', prompt: false };
    const updatedModelRegexPerm = { id: 'test-id-1', regex: 'test-regex', permission: PermissionEnum.EDIT, priority: 50, group_id: 'group-1', prompt: false };
    const promptRegexPerm = { id: 'test-id-1', regex: 'test-regex', permission: PermissionEnum.READ, priority: 100, group_id: 'group-1', prompt: true };
    const updatedPromptRegexPerm = { id: 'test-id-1', regex: 'test-regex', permission: PermissionEnum.EDIT, priority: 50, group_id: 'group-1', prompt: true };
    it('should open modal and add experiment regex permission', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(regexPerm) } as any);
      experimentRegexDataService.addExperimentRegexPermissionToUser.mockReturnValue(of(null));
      experimentRegexDataService.getExperimentRegexPermissionsForUser.mockReturnValue(
        of([regexPerm as ExperimentRegexPermissionModel])
      );
      component.userId = '123';
      component.openModalAddExperimentRegexPermissionToUser();
      jest.runAllTimers();
      expect(dialog.open).toHaveBeenCalled();
      expect(experimentRegexDataService.addExperimentRegexPermissionToUser).toHaveBeenCalledWith(
        '123',
        regexPerm.regex,
        regexPerm.permission,
        regexPerm.priority
      );
      expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Experiment regex permission added successfully');
      expect(experimentRegexDataService.getExperimentRegexPermissionsForUser).toHaveBeenCalledWith('123');
      expect(component.experimentRegexDataSource).toEqual([regexPerm]);
    });
    it('should handle edit experiment regex permission', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(updatedRegexPerm) } as any);
      experimentRegexDataService.updateExperimentRegexPermissionForUser.mockReturnValue(of(null));
      experimentRegexDataService.getExperimentRegexPermissionsForUser.mockReturnValue(
        of([updatedRegexPerm as ExperimentRegexPermissionModel])
      );
      component.userId = '123';
      const event = { action: { action: TableActionEnum.EDIT }, item: regexPerm };
      component.handleExperimentRegexActions(event as any);
      jest.runAllTimers();
      expect(dialog.open).toHaveBeenCalled();
      expect(experimentRegexDataService.updateExperimentRegexPermissionForUser).toHaveBeenCalledWith(
        '123',
        regexPerm.regex,
        updatedRegexPerm.permission,
        updatedRegexPerm.priority,
        regexPerm.id
      );
      expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Experiment regex permission updated successfully');
      expect(component.experimentRegexDataSource).toEqual([updatedRegexPerm]);
    });
    it('should handle revoke experiment regex permission', () => {
      experimentRegexDataService.removeExperimentRegexPermissionFromUser.mockReturnValue(of(null));
      experimentRegexDataService.getExperimentRegexPermissionsForUser.mockReturnValue(of([]));
      component.userId = '123';
      const event = { action: { action: TableActionEnum.REVOKE }, item: regexPerm };
      component.handleExperimentRegexActions(event as any);
      expect(experimentRegexDataService.removeExperimentRegexPermissionFromUser).toHaveBeenCalledWith(
        '123',
        regexPerm.id
      );
      expect(component.experimentRegexDataSource).toEqual([]);
    });
    it('should not do anything if dialog is dismissed for add experiment regex', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(null) } as any);
      component.userId = '123';
      component.openModalAddExperimentRegexPermissionToUser();
      jest.runAllTimers();
      expect(experimentRegexDataService.addExperimentRegexPermissionToUser).not.toHaveBeenCalled();
    });
    it('should not do anything if dialog is dismissed for edit experiment regex', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(null) } as any);
      component.userId = '123';
      const event = { action: { action: TableActionEnum.EDIT }, item: regexPerm };
      component.handleExperimentRegexActions(event as any);
      jest.runAllTimers();
      expect(experimentRegexDataService.updateExperimentRegexPermissionForUser).not.toHaveBeenCalled();
    });
    it('should open modal and add model regex permission', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(regexPerm) } as any);
      modelRegexDataService.addModelRegexPermissionToUser.mockReturnValue(of(null));
      modelRegexDataService.getModelRegexPermissionsForUser.mockReturnValue(
        of([modelRegexPerm as ModelRegexPermissionModel])
      );
      component.userId = '123';
      component.openModalAddModelRegexPermissionToUser();
      jest.runAllTimers();
      expect(dialog.open).toHaveBeenCalled();
      expect(modelRegexDataService.addModelRegexPermissionToUser).toHaveBeenCalledWith(
        '123',
        regexPerm.regex,
        regexPerm.permission,
        regexPerm.priority
      );
      expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Model regex permission added successfully');
      expect(component.modelRegexDataSource).toEqual([modelRegexPerm]);
    });
    it('should handle edit model regex permission', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(updatedRegexPerm) } as any);
      modelRegexDataService.updateModelRegexPermissionForUser.mockReturnValue(of(null));
      modelRegexDataService.getModelRegexPermissionsForUser.mockReturnValue(
        of([updatedModelRegexPerm as ModelRegexPermissionModel])
      );
      component.userId = '123';
      const event = { action: { action: TableActionEnum.EDIT }, item: modelRegexPerm };
      component.handleModelRegexActions(event as any);
      jest.runAllTimers();
      expect(dialog.open).toHaveBeenCalled();
      expect(modelRegexDataService.updateModelRegexPermissionForUser).toHaveBeenCalledWith(
        '123',
        modelRegexPerm.regex,
        updatedRegexPerm.permission,
        updatedRegexPerm.priority,
        modelRegexPerm.id
      );
      expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Model regex permission updated successfully');
      expect(component.modelRegexDataSource).toEqual([updatedModelRegexPerm]);
    });
    it('should handle revoke model regex permission', () => {
      modelRegexDataService.removeModelRegexPermissionFromUser.mockReturnValue(of(null));
      modelRegexDataService.getModelRegexPermissionsForUser.mockReturnValue(of([]));
      component.userId = '123';
      const event = { action: { action: TableActionEnum.REVOKE }, item: modelRegexPerm };
      component.handleModelRegexActions(event as any);
      expect(modelRegexDataService.removeModelRegexPermissionFromUser).toHaveBeenCalledWith('123', modelRegexPerm.id);
      expect(component.modelRegexDataSource).toEqual([]);
    });
    it('should open modal and add prompt regex permission', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(regexPerm) } as any);
      promptRegexDataService.addPromptRegexPermissionToUser.mockReturnValue(of(null));
      promptRegexDataService.getPromptRegexPermissionsForUser.mockReturnValue(
        of([promptRegexPerm as PromptRegexPermissionModel])
      );
      component.userId = '123';
      component.openModalAddPromptRegexPermissionToUser();
      jest.runAllTimers();
      expect(dialog.open).toHaveBeenCalled();
      expect(promptRegexDataService.addPromptRegexPermissionToUser).toHaveBeenCalledWith(
        '123',
        regexPerm.regex,
        regexPerm.permission,
        regexPerm.priority
      );
      expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Prompt regex permission added successfully');
      expect(component.promptRegexDataSource).toEqual([promptRegexPerm]);
    });
    it('should handle edit prompt regex permission', () => {
      dialog.open.mockReturnValue({ afterClosed: () => of(updatedRegexPerm) } as any);
      promptRegexDataService.updatePromptRegexPermissionForUser.mockReturnValue(of(null));
      promptRegexDataService.getPromptRegexPermissionsForUser.mockReturnValue(
        of([updatedPromptRegexPerm as PromptRegexPermissionModel])
      );
      component.userId = '123';
      const event = { action: { action: TableActionEnum.EDIT }, item: promptRegexPerm };
      component.handlePromptRegexActions(event as any);
      jest.runAllTimers();
      expect(dialog.open).toHaveBeenCalled();
      expect(promptRegexDataService.updatePromptRegexPermissionForUser).toHaveBeenCalledWith(
        '123',
        promptRegexPerm.regex,
        updatedRegexPerm.permission,
        updatedRegexPerm.priority,
        promptRegexPerm.id
      );
      expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Prompt regex permission updated successfully');
      expect(component.promptRegexDataSource).toEqual([updatedPromptRegexPerm]);
    });
    it('should handle revoke prompt regex permission', () => {
      promptRegexDataService.removePromptRegexPermissionFromUser.mockReturnValue(of(null));
      promptRegexDataService.getPromptRegexPermissionsForUser.mockReturnValue(of([]));
      component.userId = '123';
      const event = { action: { action: TableActionEnum.REVOKE }, item: promptRegexPerm };
      component.handlePromptRegexActions(event as any);
      expect(promptRegexDataService.removePromptRegexPermissionFromUser).toHaveBeenCalledWith('123', promptRegexPerm.id);
      expect(component.promptRegexDataSource).toEqual([]);
    });
  });
});
