import { provideHttpClient } from '@angular/common/http';
import { CUSTOM_ELEMENTS_SCHEMA, NO_ERRORS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { provideAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, Router } from '@angular/router';
import { of } from 'rxjs';
import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import {
  ExperimentModel,
  ExperimentRegexPermissionModel,
  ModelModel,
  ModelRegexPermissionModel,
  PromptRegexPermissionModel,
} from 'src/app/shared/interfaces/groups-data.interface';
import {
  AuthService,
  ExperimentRegexDataService,
  ExperimentsDataService,
  GroupDataService,
  ModelRegexDataService,
  ModelsDataService,
  PermissionDataService,
  PermissionModalService,
  PromptRegexDataService,
  PromptsDataService,
  SnackBarService,
} from 'src/app/shared/services';
import { AdminPageRoutesEnum } from '../../../config';
import { GroupPermissionDetailsComponent } from './group-permission-details.component';
describe('GroupPermissionDetailsComponent', () => {
  let component: GroupPermissionDetailsComponent;
  let fixture: ComponentFixture<GroupPermissionDetailsComponent>;
  let mockActivatedRoute: any;
  let mockRouter: Partial<Router>;
  let mockGroupDataService: Partial<GroupDataService>;
  let mockPermissionDataService: Partial<PermissionDataService>;
  let mockPermissionModalService: Partial<PermissionModalService>;
  let mockExperimentsDataService: Partial<ExperimentsDataService>;
  let mockSnackBarService: Partial<SnackBarService>;
  let mockModelDataService: Partial<ModelsDataService>;
  let mockPromptDataService: Partial<PromptsDataService>;
  let mockExperimentRegexDataService: Partial<ExperimentRegexDataService>;
  let mockModelRegexDataService: Partial<ModelRegexDataService>;
  let mockPromptRegexDataService: Partial<PromptRegexDataService>;
  let mockAuthService: Partial<AuthService>;
  let mockMatDialog: Partial<MatDialog>;
  const mockExperiment: ExperimentModel = { id: 'exp1', name: 'Experiment 1', permission: PermissionEnum.READ };
  const mockModel: ModelModel = { name: 'Model 1', permission: PermissionEnum.READ };
  const mockPrompt: ModelModel = { name: 'Prompt 1', permission: PermissionEnum.READ };
  const mockExperimentRegex: ExperimentRegexPermissionModel = {
    id: '1',
    group_id: '123',
    regex: '.*',
    permission: PermissionEnum.READ,
    priority: 100,
  };
  const mockModelRegex: ModelRegexPermissionModel = {
    id: '1',
    group_id: '123',
    regex: '.*',
    permission: PermissionEnum.READ,
    priority: 100,
    prompt: false,
  };
  const mockPromptRegex: PromptRegexPermissionModel = {
    id: '1',
    group_id: '123',
    regex: '.*',
    permission: PermissionEnum.READ,
    priority: 100,
    prompt: true,
  };
  beforeEach(async () => {
    mockActivatedRoute = {
      params: of({ id: 'testGroup' }),
      snapshot: {
        paramMap: {
          get: (key: string) => (key === 'id' ? 'testGroup' : null),
        },
        url: [{ path: AdminPageRoutesEnum.PERMISSIONS }],
      },
      parent: {
        snapshot: {
          url: [{ path: 'experiments' }],
        },
      },
    };
    mockRouter = {
      navigate: jest.fn().mockResolvedValue(true),
    };
    mockGroupDataService = {
      getAllExperimentsForGroup: jest.fn().mockReturnValue(of([mockExperiment])),
      getAllRegisteredModelsForGroup: jest.fn().mockReturnValue(of([mockModel])),
      getAllPromptsForGroup: jest.fn().mockReturnValue(of([mockPrompt])),
    };
    mockPermissionDataService = {
      addExperimentPermissionToGroup: jest.fn().mockReturnValue(of(null)),
      updateExperimentPermissionForGroup: jest.fn().mockReturnValue(of(null)),
      removeExperimentPermissionFromGroup: jest.fn().mockReturnValue(of(null)),
      addModelPermissionToGroup: jest.fn().mockReturnValue(of(null)),
      updateModelPermissionForGroup: jest.fn().mockReturnValue(of(null)),
      removeModelPermissionFromGroup: jest.fn().mockReturnValue(of(null)),
      addPromptPermissionToGroup: jest.fn().mockReturnValue(of(null)),
      updatePromptPermissionForGroup: jest.fn().mockReturnValue(of(null)),
      removePromptPermissionFromGroup: jest.fn().mockReturnValue(of(null)),
    };
    mockPermissionModalService = {
      openGrantPermissionModal: jest
        .fn()
        .mockReturnValue(of({ entity: { id: 'newExp', name: 'New Exp' }, permission: PermissionEnum.EDIT })),
      openEditPermissionsModal: jest.fn().mockReturnValue(of(PermissionEnum.MANAGE)),
    };
    mockExperimentsDataService = {
      getAllExperiments: jest.fn().mockReturnValue(of([])),
    };
    mockSnackBarService = {
      openSnackBar: jest.fn(),
    };
    mockModelDataService = {
      getAllModels: jest.fn().mockReturnValue(of([])),
    };
    mockPromptDataService = {
      getAllPrompts: jest.fn().mockReturnValue(of([])),
    };
    mockExperimentRegexDataService = {
      getExperimentRegexPermissionsForGroup: jest.fn().mockReturnValue(of([mockExperimentRegex])),
      addExperimentRegexPermissionToGroup: jest.fn().mockReturnValue(of(null)),
      updateExperimentRegexPermissionForGroup: jest.fn().mockReturnValue(of(null)),
      removeExperimentRegexPermissionFromGroup: jest.fn().mockReturnValue(of(null)),
    };
    mockModelRegexDataService = {
      getModelRegexPermissionsForGroup: jest.fn().mockReturnValue(of([mockModelRegex])),
      addModelRegexPermissionToGroup: jest.fn().mockReturnValue(of(null)),
      updateModelRegexPermissionForGroup: jest.fn().mockReturnValue(of(null)),
      removeModelRegexPermissionFromGroup: jest.fn().mockReturnValue(of(null)),
    };
    mockPromptRegexDataService = {
      getPromptRegexPermissionsForGroup: jest.fn().mockReturnValue(of([mockPromptRegex])),
      addPromptRegexPermissionToGroup: jest.fn().mockReturnValue(of(null)),
      updatePromptRegexPermissionForGroup: jest.fn().mockReturnValue(of(null)),
      removePromptRegexPermissionFromGroup: jest.fn().mockReturnValue(of(null)),
    };
    mockAuthService = {
      getUserInfo: jest.fn().mockReturnValue({ is_admin: false }),
    };
    mockMatDialog = {
      open: jest.fn().mockReturnValue({
        afterClosed: () => of({ regex: '.*', permission: PermissionEnum.READ, priority: 100 }),
      } as any),
    };
    await TestBed.configureTestingModule({
      declarations: [GroupPermissionDetailsComponent],
      imports: [MatTabsModule, MatIconModule],
      providers: [
        provideHttpClient(),
        provideAnimations(),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        { provide: Router, useValue: mockRouter },
        { provide: GroupDataService, useValue: mockGroupDataService },
        { provide: PermissionDataService, useValue: mockPermissionDataService },
        { provide: PermissionModalService, useValue: mockPermissionModalService },
        { provide: ExperimentsDataService, useValue: mockExperimentsDataService },
        { provide: SnackBarService, useValue: mockSnackBarService },
        { provide: ModelsDataService, useValue: mockModelDataService },
        { provide: PromptsDataService, useValue: mockPromptDataService },
        { provide: ExperimentRegexDataService, useValue: mockExperimentRegexDataService },
        { provide: ModelRegexDataService, useValue: mockModelRegexDataService },
        { provide: PromptRegexDataService, useValue: mockPromptRegexDataService },
        { provide: AuthService, useValue: mockAuthService },
        { provide: MatDialog, useValue: mockMatDialog },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA, NO_ERRORS_SCHEMA],
    }).compileComponents();
    fixture = TestBed.createComponent(GroupPermissionDetailsComponent);
    component = fixture.componentInstance;
  });
  it('should create', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });
  describe('ngOnInit', () => {
    it('should initialize groupName and isAdmin', () => {
      (mockAuthService.getUserInfo as jest.Mock).mockReturnValue({ is_admin: true });
      fixture.detectChanges();
      expect(component.groupName).toBe('testGroup');
      expect(component.isAdmin).toBe(true);
      expect(mockGroupDataService.getAllExperimentsForGroup).toHaveBeenCalledWith('testGroup');
      expect(mockGroupDataService.getAllRegisteredModelsForGroup).toHaveBeenCalledWith('testGroup');
      expect(mockGroupDataService.getAllPromptsForGroup).toHaveBeenCalledWith('testGroup');
      expect(mockExperimentRegexDataService.getExperimentRegexPermissionsForGroup).toHaveBeenCalledWith('testGroup');
      expect(mockModelRegexDataService.getModelRegexPermissionsForGroup).toHaveBeenCalledWith('testGroup');
      expect(mockPromptRegexDataService.getPromptRegexPermissionsForGroup).toHaveBeenCalledWith('testGroup');
    });
    it('should set selectedSubTabIndexes based on route', () => {
      mockActivatedRoute.snapshot.url = [{ path: AdminPageRoutesEnum.REGEX }];
      mockActivatedRoute.parent.snapshot.url = [{ path: 'models' }];
      fixture.detectChanges();
      expect(component.selectedSubTabIndexes).toEqual([0, 1, 0]);
    });
    it('should default subTab index for first main tab to permissions when no route parts present', () => {
      mockActivatedRoute.parent.snapshot.url = [];
      mockActivatedRoute.snapshot.url = [];
      fixture.detectChanges();
      expect(component.selectedSubTabIndexes[0]).toBe(0);
    });
    it('should default to permissions sub-tab if subRoutePath is not present', () => {
      mockActivatedRoute.snapshot.url = [];
      mockActivatedRoute.parent.snapshot.url = [{ path: 'experiments' }];
      fixture.detectChanges();
      expect(component.selectedSubTabIndexes[0]).toBe(0);
    });
  });
  describe('ngAfterViewInit', () => {
    it('should set permissionsTabs.selectedIndex to permissions sub-tab index based on route after view init', () => {
      component.permissionsTabs = { selectedIndex: -1 } as any;
      mockActivatedRoute.parent.snapshot.url = [{ path: 'models' }];
      fixture.detectChanges();
      component.ngAfterViewInit();
      jest.runAllTimers();
      expect(component.permissionsTabs.selectedIndex).toBe(0);
    });
    it('should default permissionsTabs selectedIndex to 0 if mainEntityPath is not found', () => {
      component.permissionsTabs = { selectedIndex: -1 } as any;
      mockActivatedRoute.parent.snapshot.url = [{ path: 'invalidPath' }];
      fixture.detectChanges();
      component.ngAfterViewInit();
      expect(component.permissionsTabs.selectedIndex).toBe(0);
    });
  });
  it('should complete destroy$ on ngOnDestroy', () => {
    const destroyNextSpy = jest.spyOn((component as any).destroy$, 'next');
    const destroyCompleteSpy = jest.spyOn((component as any).destroy$, 'complete');
    fixture.detectChanges();
    component.ngOnDestroy();
    expect(destroyNextSpy).toHaveBeenCalled();
    expect(destroyCompleteSpy).toHaveBeenCalled();
  });
  describe('Permission Modals and Handling', () => {
    beforeEach(() => {
      fixture.detectChanges();
    });
    it('openModalAddExperimentPermissionToGroup should add permission and refresh data', () => {
      (mockExperimentsDataService.getAllExperiments as jest.Mock).mockReturnValue(
        of([{ name: 'New Exp', id: 'newExpId' }])
      );
      component.openModalAddExperimentPermissionToGroup();
      expect(mockPermissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
        EntityEnum.EXPERIMENT,
        expect.any(Array),
        'testGroup'
      );
      expect(mockPermissionDataService.addExperimentPermissionToGroup).toHaveBeenCalledWith(
        'testGroup',
        'newExp',
        PermissionEnum.EDIT
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission granted successfully');
      expect(mockGroupDataService.getAllExperimentsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handleExperimentActions EDIT should call handleEditExperimentPermissionForGroup', () => {
      const handleEditSpy = jest.spyOn(component, 'handleEditExperimentPermissionForGroup');
      component.handleExperimentActions({
        action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
        item: mockExperiment,
      });
      expect(handleEditSpy).toHaveBeenCalledWith(mockExperiment);
    });
    it('handleExperimentActions REVOKE should call revokeExperimentPermissionForGroup', () => {
      const revokeSpy = jest.spyOn(component, 'revokeExperimentPermissionForGroup');
      component.handleExperimentActions({
        action: { action: TableActionEnum.REVOKE, icon: 'delete', name: 'Revoke' },
        item: mockExperiment,
      });
      expect(revokeSpy).toHaveBeenCalledWith(mockExperiment);
    });
    it('handleEditExperimentPermissionForGroup should update permission and refresh data', () => {
      component.handleEditExperimentPermissionForGroup(mockExperiment);
      expect(mockPermissionModalService.openEditPermissionsModal).toHaveBeenCalledWith(
        mockExperiment.name,
        'testGroup',
        mockExperiment.permission
      );
      expect(mockPermissionDataService.updateExperimentPermissionForGroup).toHaveBeenCalledWith(
        'testGroup',
        mockExperiment.id,
        PermissionEnum.MANAGE
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission updated successfully');
      expect(mockGroupDataService.getAllExperimentsForGroup).toHaveBeenCalledTimes(2);
    });
    it('revokeExperimentPermissionForGroup should remove permission and refresh data', () => {
      component.revokeExperimentPermissionForGroup(mockExperiment);
      expect(mockPermissionDataService.removeExperimentPermissionFromGroup).toHaveBeenCalledWith(
        'testGroup',
        mockExperiment.id
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
      expect(mockGroupDataService.getAllExperimentsForGroup).toHaveBeenCalledTimes(2);
    });
    it('openModalAddModelPermissionToGroup should add permission and refresh data', () => {
      (mockModelDataService.getAllModels as jest.Mock).mockReturnValue(of([{ name: 'New Model' }]));
      component.openModalAddModelPermissionToGroup();
      expect(mockPermissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
        EntityEnum.MODEL,
        expect.any(Array),
        'testGroup'
      );
      expect(mockPermissionDataService.addModelPermissionToGroup).toHaveBeenCalledWith(
        'New Exp',
        'testGroup',
        PermissionEnum.EDIT
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission granted successfully');
      expect(mockGroupDataService.getAllRegisteredModelsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handleModelActions EDIT should call handleEditModelPermissionForGroup', () => {
      const handleEditSpy = jest.spyOn(component, 'handleEditModelPermissionForGroup');
      component.handleModelActions({
        action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
        item: mockModel,
      });
      expect(handleEditSpy).toHaveBeenCalledWith(mockModel);
    });
    it('handleModelActions REVOKE should call revokeModelPermissionForGroup', () => {
      const revokeSpy = jest.spyOn(component, 'revokeModelPermissionForGroup');
      component.handleModelActions({
        action: { action: TableActionEnum.REVOKE, icon: 'delete', name: 'Revoke' },
        item: mockModel,
      });
      expect(revokeSpy).toHaveBeenCalledWith(mockModel);
    });
    it('handleEditModelPermissionForGroup should update permission and refresh data', () => {
      component.handleEditModelPermissionForGroup(mockModel);
      expect(mockPermissionModalService.openEditPermissionsModal).toHaveBeenCalledWith(
        mockModel.name,
        'testGroup',
        mockModel.permission
      );
      expect(mockPermissionDataService.updateModelPermissionForGroup).toHaveBeenCalledWith(
        mockModel.name,
        'testGroup',
        PermissionEnum.MANAGE
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission updated successfully');
      expect(mockGroupDataService.getAllRegisteredModelsForGroup).toHaveBeenCalledTimes(2);
    });
    it('revokeModelPermissionForGroup should remove permission and refresh data', () => {
      component.revokeModelPermissionForGroup(mockModel);
      expect(mockPermissionDataService.removeModelPermissionFromGroup).toHaveBeenCalledWith(
        mockModel.name,
        'testGroup'
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
      expect(mockGroupDataService.getAllRegisteredModelsForGroup).toHaveBeenCalledTimes(2);
    });
    it('openModalAddPromptPermissionToGroup should add permission and refresh data', () => {
      (mockPromptDataService.getAllPrompts as jest.Mock).mockReturnValue(of([{ name: 'New Prompt' }]));
      component.openModalAddPromptPermissionToGroup();
      expect(mockPermissionModalService.openGrantPermissionModal).toHaveBeenCalledWith(
        EntityEnum.PROMPT,
        expect.any(Array),
        'testGroup'
      );
      expect(mockPermissionDataService.addPromptPermissionToGroup).toHaveBeenCalledWith(
        'New Exp',
        'testGroup',
        PermissionEnum.EDIT
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission granted successfully');
      expect(mockGroupDataService.getAllPromptsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handlePromptActions EDIT should call handleEditPromptPermissionForGroup', () => {
      const handleEditSpy = jest.spyOn(component, 'handleEditPromptPermissionForGroup');
      component.handlePromptActions({
        action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
        item: mockPrompt,
      });
      expect(handleEditSpy).toHaveBeenCalledWith(mockPrompt);
    });
    it('handlePromptActions REVOKE should call revokePromptPermissionForGroup', () => {
      const revokeSpy = jest.spyOn(component, 'revokePromptPermissionForGroup');
      component.handlePromptActions({
        action: { action: TableActionEnum.REVOKE, icon: 'delete', name: 'Revoke' },
        item: mockPrompt,
      });
      expect(revokeSpy).toHaveBeenCalledWith(mockPrompt);
    });
    it('handleEditPromptPermissionForGroup should update permission and refresh data', () => {
      component.handleEditPromptPermissionForGroup(mockPrompt);
      expect(mockPermissionModalService.openEditPermissionsModal).toHaveBeenCalledWith(
        mockPrompt.name,
        'testGroup',
        mockPrompt.permission
      );
      expect(mockPermissionDataService.updatePromptPermissionForGroup).toHaveBeenCalledWith(
        mockPrompt.name,
        'testGroup',
        PermissionEnum.MANAGE
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission updated successfully');
      expect(mockGroupDataService.getAllPromptsForGroup).toHaveBeenCalledTimes(2);
    });
    it('revokePromptPermissionForGroup should remove permission and refresh data', () => {
      component.revokePromptPermissionForGroup(mockPrompt);
      expect(mockPermissionDataService.removePromptPermissionFromGroup).toHaveBeenCalledWith(
        mockPrompt.name,
        'testGroup'
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Permission revoked successfully');
      expect(mockGroupDataService.getAllPromptsForGroup).toHaveBeenCalledTimes(2);
    });
  });
  describe('Tab Navigation', () => {
    beforeEach(() => {
      if (typeof global.setTimeout !== 'function') {
        const mockSetTimeout: any = jest.fn((fn: Function) => {
          fn();
          return 0;
        });
        mockSetTimeout.__promisify__ = () => Promise.resolve(0);
        (global as any).setTimeout = mockSetTimeout;
      }
      if (typeof global.queueMicrotask !== 'function') {
        global.queueMicrotask = (fn: Function) => Promise.resolve().then(() => fn());
      }
      fixture.detectChanges();
      component.permissionsTabs = { selectedIndex: 0 } as any;
      (component as any).isMainTabInit = false;
    });
    it('handleTabSelection should navigate to the correct route', () => {
      (component as any).isMainTabInit = false;
      component.handleTabSelection(1);
      jest.runAllTimers();
      expect(mockRouter.navigate).toHaveBeenCalledWith(['/manage/group/testGroup/models/permissions']);
    });
    it('handleTabSelection should navigate if isMainTabInit is true', () => {
      component.handleTabSelection(1);
      expect(mockRouter.navigate).toHaveBeenCalled();
    });
    it('handleSubTabSelection should navigate to the correct sub-route (permissions)', () => {
      component.handleSubTabSelection(0);
      expect(mockRouter.navigate).toHaveBeenCalledWith(['/manage/group/testGroup/experiments/permissions']);
      expect(component.selectedSubTabIndexes[0]).toBe(0);
    });
    it('handleSubTabSelection should navigate to the correct sub-route (regex)', () => {
      component.permissionsTabs.selectedIndex = 1;
      component.handleSubTabSelection(1);
      expect(mockRouter.navigate).toHaveBeenCalledWith(['/manage/group/testGroup/models/regex']);
      expect(component.selectedSubTabIndexes[1]).toBe(1);
    });
    it('handleSubTabSelection should not navigate if navigating is true', () => {
      (component as any).navigating = true;
      component.handleSubTabSelection(0);
      expect(mockRouter.navigate).not.toHaveBeenCalled();
    });
  });
  describe('Regex Permission Modals and Handling (Admin Only)', () => {
    beforeEach(() => {
      (mockAuthService.getUserInfo as jest.Mock).mockReturnValue({ is_admin: true });
      fixture.detectChanges();
    });
    it('openModalAddExperimentRegexPermissionToGroup should add permission and refresh data', () => {
      component.openModalAddExperimentRegexPermissionToGroup();
      expect(mockMatDialog.open).toHaveBeenCalled();
      expect(mockExperimentRegexDataService.addExperimentRegexPermissionToGroup).toHaveBeenCalledWith(
        'testGroup',
        '.*',
        PermissionEnum.READ,
        100
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Experiment regex permission added successfully');
      expect(mockExperimentRegexDataService.getExperimentRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handleExperimentRegexActions EDIT should open modal, update permission and refresh data', () => {
      component.handleExperimentRegexActions({
        action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
        item: mockExperimentRegex,
      });
      expect(mockMatDialog.open).toHaveBeenCalled();
      expect(mockExperimentRegexDataService.updateExperimentRegexPermissionForGroup).toHaveBeenCalledWith(
        'testGroup',
        mockExperimentRegex.regex,
        PermissionEnum.READ,
        100,
        mockExperimentRegex.id
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Experiment regex permission updated successfully');
      expect(mockExperimentRegexDataService.getExperimentRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handleExperimentRegexActions REVOKE should remove permission and refresh data', () => {
      component.handleExperimentRegexActions({
        action: { action: TableActionEnum.REVOKE, icon: 'delete', name: 'Revoke' },
        item: mockExperimentRegex,
      });
      expect(mockExperimentRegexDataService.removeExperimentRegexPermissionFromGroup).toHaveBeenCalledWith(
        'testGroup',
        mockExperimentRegex.id
      );
      expect(mockExperimentRegexDataService.getExperimentRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('openModalAddModelRegexPermissionToGroup should add permission and refresh data', () => {
      component.openModalAddModelRegexPermissionToGroup();
      expect(mockMatDialog.open).toHaveBeenCalled();
      expect(mockModelRegexDataService.addModelRegexPermissionToGroup).toHaveBeenCalledWith(
        'testGroup',
        '.*',
        PermissionEnum.READ,
        100
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Model regex permission added successfully');
      expect(mockModelRegexDataService.getModelRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handleModelRegexActions EDIT should open modal, update permission and refresh data', () => {
      component.handleModelRegexActions({
        action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
        item: mockModelRegex,
      });
      expect(mockMatDialog.open).toHaveBeenCalled();
      expect(mockModelRegexDataService.updateModelRegexPermissionForGroup).toHaveBeenCalledWith(
        'testGroup',
        mockModelRegex.regex,
        PermissionEnum.READ,
        100,
        mockModelRegex.id
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Model regex permission updated successfully');
      expect(mockModelRegexDataService.getModelRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handleModelRegexActions REVOKE should remove permission and refresh data', () => {
      component.handleModelRegexActions({
        action: { action: TableActionEnum.REVOKE, icon: 'delete', name: 'Revoke' },
        item: mockModelRegex,
      });
      expect(mockModelRegexDataService.removeModelRegexPermissionFromGroup).toHaveBeenCalledWith(
        'testGroup',
        mockModelRegex.id
      );
      expect(mockModelRegexDataService.getModelRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('openModalAddPromptRegexPermissionToGroup should add permission and refresh data', () => {
      component.openModalAddPromptRegexPermissionToGroup();
      expect(mockMatDialog.open).toHaveBeenCalled();
      expect(mockPromptRegexDataService.addPromptRegexPermissionToGroup).toHaveBeenCalledWith(
        'testGroup',
        '.*',
        PermissionEnum.READ,
        100
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Prompt regex permission added successfully');
      expect(mockPromptRegexDataService.getPromptRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handlePromptRegexActions EDIT should open modal, update permission and refresh data', () => {
      component.handlePromptRegexActions({
        action: { action: TableActionEnum.EDIT, icon: 'edit', name: 'Edit' },
        item: mockPromptRegex,
      });
      expect(mockMatDialog.open).toHaveBeenCalled();
      expect(mockPromptRegexDataService.updatePromptRegexPermissionForGroup).toHaveBeenCalledWith(
        'testGroup',
        mockPromptRegex.regex,
        PermissionEnum.READ,
        100,
        mockPromptRegex.id
      );
      expect(mockSnackBarService.openSnackBar).toHaveBeenCalledWith('Prompt regex permission updated successfully');
      expect(mockPromptRegexDataService.getPromptRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('handlePromptRegexActions REVOKE should remove permission and refresh data', () => {
      component.handlePromptRegexActions({
        action: { action: TableActionEnum.REVOKE, icon: 'delete', name: 'Revoke' },
        item: mockPromptRegex,
      });
      expect(mockPromptRegexDataService.removePromptRegexPermissionFromGroup).toHaveBeenCalledWith(
        'testGroup',
        mockPromptRegex.id
      );
      expect(mockPromptRegexDataService.getPromptRegexPermissionsForGroup).toHaveBeenCalledTimes(2);
    });
    it('should not call regex data services if not admin in ngOnInit', () => {
      if (typeof global.setTimeout !== 'function') {
        const mockSetTimeout: any = jest.fn((fn: Function) => {
          fn();
          return 0;
        });
        mockSetTimeout.__promisify__ = () => Promise.resolve(0);
        (global as any).setTimeout = mockSetTimeout;
      }
      if (typeof global.queueMicrotask !== 'function') {
        global.queueMicrotask = (fn: Function) => Promise.resolve().then(() => fn());
      }
      jest.clearAllMocks();
      (mockAuthService.getUserInfo as jest.Mock).mockReturnValue({ is_admin: false });
      TestBed.resetTestingModule();
      TestBed.configureTestingModule({
        declarations: [GroupPermissionDetailsComponent],
        imports: [MatTabsModule, MatIconModule],
        providers: [
          provideHttpClient(),
          provideAnimations(),
          { provide: ActivatedRoute, useValue: mockActivatedRoute },
          { provide: Router, useValue: mockRouter },
          { provide: GroupDataService, useValue: mockGroupDataService },
          { provide: PermissionDataService, useValue: mockPermissionDataService },
          { provide: PermissionModalService, useValue: mockPermissionModalService },
          { provide: ExperimentsDataService, useValue: mockExperimentsDataService },
          { provide: SnackBarService, useValue: mockSnackBarService },
          { provide: ModelsDataService, useValue: mockModelDataService },
          { provide: PromptsDataService, useValue: mockPromptDataService },
          { provide: ExperimentRegexDataService, useValue: mockExperimentRegexDataService },
          { provide: ModelRegexDataService, useValue: mockModelRegexDataService },
          { provide: PromptRegexDataService, useValue: mockPromptRegexDataService },
          { provide: AuthService, useValue: mockAuthService },
          { provide: MatDialog, useValue: mockMatDialog },
        ],
        schemas: [CUSTOM_ELEMENTS_SCHEMA, NO_ERRORS_SCHEMA],
      }).compileComponents();
      fixture = TestBed.createComponent(GroupPermissionDetailsComponent);
      component = fixture.componentInstance;
      fixture.detectChanges();
      jest.runAllTimers();
      expect(component.isAdmin).toBe(false);
      expect(mockExperimentRegexDataService.getExperimentRegexPermissionsForGroup).not.toHaveBeenCalled();
      expect(mockModelRegexDataService.getModelRegexPermissionsForGroup).not.toHaveBeenCalled();
      expect(mockPromptRegexDataService.getPromptRegexPermissionsForGroup).not.toHaveBeenCalled();
    });
  });
});
