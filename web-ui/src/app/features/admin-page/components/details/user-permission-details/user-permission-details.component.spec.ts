import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatTabsModule } from '@angular/material/tabs';
import { provideAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { UserPermissionDetailsComponent } from './user-permission-details.component';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { MatTabGroup } from '@angular/material/tabs';
import { Router } from '@angular/router';
import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum, PermissionTypeEnum } from 'src/app/core/configs/permissions';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { ExperimentForUserModel } from 'src/app/shared/interfaces/experiments-data.interface';
import { ModelPermissionModel } from 'src/app/shared/interfaces/models-data.interface';
import {
  ExperimentsDataService,
  ModelsDataService,
  PermissionDataService,
  SnackBarService,
  ExperimentRegexDataService,
  ModelRegexDataService,
  PromptRegexDataService,
  AuthService,
  PromptsDataService,
} from 'src/app/shared/services';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service'; // Corrected import path
import { UserExperimentRegexDataService } from 'src/app/shared/services/data/user-experiment-regex-data.service';
import { UserModelRegexDataService } from 'src/app/shared/services/data/user-model-regex-data.service';
import { UserPromptRegexDataService } from 'src/app/shared/services/data/user-prompt-regex-data.service';
import { UserDataService } from 'src/app/shared/services/data/user-data.service';
import { jest } from '@jest/globals';

describe('UserPermissionDetailsComponent', () => {
  let component: UserPermissionDetailsComponent;
  let fixture: ComponentFixture<UserPermissionDetailsComponent>;
  let expDataService: jest.Mocked<ExperimentsDataService>;
  let modelDataService: jest.Mocked<ModelsDataService>;
  let promptDataService: jest.Mocked<PromptsDataService>; // Corrected type
  let permissionDataService: jest.Mocked<PermissionDataService>;
  let experimentRegexDataService: jest.Mocked<UserExperimentRegexDataService>; // Corrected type
  let modelRegexDataService: jest.Mocked<UserModelRegexDataService>; // Corrected type
  let promptRegexDataService: jest.Mocked<UserPromptRegexDataService>; // Corrected type
  let permissionModalService: jest.Mocked<PermissionModalService>;
  let snackBarService: jest.Mocked<SnackBarService>;
  let router: jest.Mocked<Router>;
  let activatedRoute: ActivatedRoute;
  let authService: jest.Mocked<AuthService>;
  let userDataService: jest.Mocked<UserDataService>;

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
      navigate: jest.fn(),
    } as any;

    authService = {
      getUserInfo: jest.fn().mockReturnValue({ is_admin: false }),
    } as any;

    userDataService = {
      getUser: jest.fn().mockReturnValue(of(null)),
    } as any;

    activatedRoute = {
      params: of({ id: '123' }),
      snapshot: {
        paramMap: { get: (key: string) => (key === 'id' ? '123' : null) },
        url: [{ path: 'admin' }, { path: 'details' }, { path: 'models' }],
      },
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
        { provide: PromptsDataService, useValue: promptDataService }, // Corrected provider
        { provide: PermissionDataService, useValue: permissionDataService },
        { provide: UserExperimentRegexDataService, useValue: experimentRegexDataService },
        { provide: UserModelRegexDataService, useValue: modelRegexDataService },
        { provide: UserPromptRegexDataService, useValue: promptRegexDataService },
        { provide: PermissionModalService, useValue: permissionModalService }, // Corrected provider
        { provide: SnackBarService, useValue: snackBarService },
        { provide: Router, useValue: router },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ id: 'testUser' }),
              url: [], // Provide a default empty array for url
            },
          },
        },
        { provide: AuthService, useValue: authService },
        { provide: UserDataService, useValue: userDataService },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(UserPermissionDetailsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
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

    component.ngOnInit();
    expect(expDataService.getExperimentsForUser).toHaveBeenCalledWith('123');
    expect(modelDataService.getModelsForUser).toHaveBeenCalledWith('123');
    expect(promptDataService.getPromptsForUser).toHaveBeenCalledWith('123');
    expect(component.experimentsDataSource).toEqual(experiments);
    expect(component.modelsDataSource).toEqual(models);
    expect(component.promptsDataSource).toEqual(prompts);
  });

  // it("should set tab index on ngAfterViewInit", () => {
  //   component.permissionsTabs = { selectedIndex: 0 } as MatTabGroup;
  //   component.ngAfterViewInit();
  //   expect(component.permissionsTabs.selectedIndex).toBe(1);
  // });

  it('should add model permission to user', () => {
    modelDataService.getAllModels.mockReturnValue(
      of([
        {
          name: 'model2',
          aliases: {},
          description: '',
          tags: {},
        },
      ])
    );
    permissionModalService.openGrantPermissionModal.mockReturnValue(
      of({
        entity: { id: '0', name: 'model2' },
        permission: PermissionEnum.EDIT,
      })
    );
    permissionDataService.createModelPermission.mockReturnValue(of('created'));
    modelDataService.getModelsForUser.mockReturnValue(
      of([
        {
          name: 'model2',
          permission: PermissionEnum.EDIT,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.modelsDataSource = [
      {
        name: 'model1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    ];
    component.addModelPermissionToUser();
    expect(modelDataService.getAllModels).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalled();
    expect(permissionDataService.createModelPermission).toHaveBeenCalledWith({
      username: '123',
      name: 'model2',
      permission: PermissionEnum.EDIT,
    });
    expect(modelDataService.getModelsForUser).toHaveBeenCalledWith('123');
  });

  it('should add experiment permission to user', () => {
    expDataService.getAllExperiments.mockReturnValue(
      of([
        {
          id: 'exp2',
          name: 'Experiment 2',
          tags: {},
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    permissionModalService.openGrantPermissionModal.mockReturnValue(
      of({
        entity: { id: 'exp2', name: 'Experiment 2' },
        permission: PermissionEnum.READ,
      })
    );
    permissionDataService.createExperimentPermission.mockReturnValue(of('created'));
    expDataService.getExperimentsForUser.mockReturnValue(
      of([
        {
          id: 'exp2',
          name: 'Experiment 2',
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.USER,
        },
      ])
    );
    component.userId = '123';
    component.experimentsDataSource = [
      {
        id: 'exp1',
        name: 'Experiment 1',
        permission: PermissionEnum.READ,
        type: PermissionTypeEnum.USER,
      },
    ];
    component.addExperimentPermissionToUser();
    expect(expDataService.getAllExperiments).toHaveBeenCalled();
    expect(permissionModalService.openGrantPermissionModal).toHaveBeenCalled();
    expect(permissionDataService.createExperimentPermission).toHaveBeenCalledWith({
      username: '123',
      experiment_name: 'Experiment 2',
      permission: PermissionEnum.READ,
    });
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
    snackBarService.openSnackBar.mockReturnValue({} as any);
    component.revokePromptPermissionForUser({
      name: 'prompt1',
      permission: PermissionEnum.READ,
      type: PermissionTypeEnum.FALLBACK,
    } as any);
    expect(snackBarService.openSnackBar).toHaveBeenCalledWith('Nothing to reset');
  });

  it('should handle tab selection', () => {
    component.userId = '123';
    (component as any).isMainTabInit = false; // Ensure this is false for the test to proceed
    component.permissionsTabs = { selectedIndex: 2 } as MatTabGroup; // Mock selectedIndex for main tab
    component.handleTabSelection(2);
    expect(router.navigate).toHaveBeenCalledWith([`/manage/user/123/prompts/permissions`]);
  });
});
