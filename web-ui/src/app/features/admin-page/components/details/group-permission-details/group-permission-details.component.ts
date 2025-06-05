import { Component, OnInit, ViewChild, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { filter, map, switchMap, tap, takeUntil } from 'rxjs';
import { MatDialog } from '@angular/material/dialog';
import { Subject } from 'rxjs';

import { MatTabGroup } from '@angular/material/tabs';
import { EntityEnum } from 'src/app/core/configs/core';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import {
  TableActionEvent,
  TableActionModel,
  TableColumnConfigModel,
} from 'src/app/shared/components/table/table.interface';
import {
  ExperimentModel,
  ModelModel,
  ExperimentRegexPermissionModel,
  ModelRegexPermissionModel,
  PromptRegexPermissionModel,
} from 'src/app/shared/interfaces/groups-data.interface';
import {
  ExperimentsDataService,
  ModelsDataService,
  PermissionDataService,
  PromptsDataService,
  SnackBarService,
  ExperimentRegexDataService,
  ModelRegexDataService,
  PromptRegexDataService,
} from 'src/app/shared/services';
import { GroupDataService } from 'src/app/shared/services/data/group-data.service';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service';
import {
  EXPERIMENT_ACTIONS,
  EXPERIMENT_COLUMN_CONFIG,
  MODELS_ACTIONS,
  MODELS_COLUMN_CONFIG,
  PROMPTS_ACTIONS,
  PROMPTS_COLUMN_CONFIG,
  EXPERIMENT_REGEX_COLUMN_CONFIG,
  EXPERIMENT_REGEX_ACTIONS,
  MODELS_REGEX_COLUMN_CONFIG,
  MODELS_REGEX_ACTIONS,
  PROMPTS_REGEX_COLUMN_CONFIG,
  PROMPTS_REGEX_ACTIONS,
} from './group-permission-details.config';
import { AuthService } from 'src/app/shared/services/auth.service';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { AdminPageRoutesEnum } from '../../../config';
import { ManageRegexModalComponent } from 'src/app/shared/components/modals/manage-regex-modal/manage-regex-modal.component';
import { ManageRegexModalData } from 'src/app/shared/components/modals/manage-regex-modal/manage-regex-modal.interface';

@Component({
  selector: 'ml-group-permission-details',
  templateUrl: './group-permission-details.component.html',
  styleUrls: ['./group-permission-details.component.scss'],
  standalone: false,
})
export class GroupPermissionDetailsComponent implements OnInit, OnDestroy {
  selectedSubTabIndexes: number[] = [0, 0, 0];
  private navigating = false;

  groupName = '';

  experimentColumnConfig: TableColumnConfigModel[] = EXPERIMENT_COLUMN_CONFIG;
  experimentDataSource: ExperimentModel[] = [];
  experimentActions: TableActionModel[] = EXPERIMENT_ACTIONS;

  modelColumnConfig: TableColumnConfigModel[] = MODELS_COLUMN_CONFIG;
  modelDataSource: ModelModel[] = [];
  modelActions: TableActionModel[] = MODELS_ACTIONS;

  promptColumnConfig: TableColumnConfigModel[] = PROMPTS_COLUMN_CONFIG;
  promptDataSource: ModelModel[] = [];
  promptActions: TableActionModel[] = PROMPTS_ACTIONS;

  // admin flag
  isAdmin = false;

  // regex permissions configs and data sources
  experimentRegexColumnConfig = EXPERIMENT_REGEX_COLUMN_CONFIG;
  experimentRegexDataSource: ExperimentRegexPermissionModel[] = [];
  experimentRegexActions = EXPERIMENT_REGEX_ACTIONS;

  modelRegexColumnConfig = MODELS_REGEX_COLUMN_CONFIG;
  modelRegexDataSource: ModelRegexPermissionModel[] = [];
  modelRegexActions = MODELS_REGEX_ACTIONS;

  promptRegexColumnConfig = PROMPTS_REGEX_COLUMN_CONFIG;
  promptRegexDataSource: PromptRegexPermissionModel[] = [];
  promptRegexActions = PROMPTS_REGEX_ACTIONS;

  @ViewChild('permissionsTabs') permissionsTabs!: MatTabGroup;

  private readonly tabIndexMapping: string[] = ['experiments', 'models', 'prompts'];
  private isMainTabInit = true;
  private destroy$ = new Subject<void>();

  constructor(
    private readonly groupDataService: GroupDataService,
    private readonly route: ActivatedRoute,
    private readonly permissionDataService: PermissionDataService,
    private readonly permissionModalService: PermissionModalService,
    private readonly experimentsDataService: ExperimentsDataService,
    private readonly snackBarService: SnackBarService,
    private readonly modelDataService: ModelsDataService,
    private readonly promptDataService: PromptsDataService,
    private readonly experimentRegexDataService: ExperimentRegexDataService,
    private readonly modelRegexDataService: ModelRegexDataService,
    private readonly promptRegexDataService: PromptRegexDataService,
    private readonly router: Router,
    private readonly authService: AuthService,
    private readonly dialog: MatDialog
  ) {}

  ngOnInit(): void {
    this.groupName = this.route.snapshot.paramMap.get('id') ?? '';
    this.isAdmin = this.authService.getUserInfo().is_admin;

    const mainEntityPath = this.route.parent?.snapshot.url[0]?.path;
    const subRoutePath = this.route.snapshot.url[0]?.path;

    let determinedMainTabIndex = mainEntityPath ? this.tabIndexMapping.indexOf(mainEntityPath) : -1;
    if (determinedMainTabIndex === -1) {
      determinedMainTabIndex = 0; // Default to the first main tab if entity not found or invalid
    }

    // selectedSubTabIndexes is initialized as [0, 0, 0] in the class property.
    // Update the correct sub-tab index based on the route.
    if (subRoutePath) {
      this.selectedSubTabIndexes[determinedMainTabIndex] = subRoutePath === AdminPageRoutesEnum.REGEX ? 1 : 0;
    } else {
      // Default to 'permissions' sub-tab (index 0) if subRoutePath is not present
      this.selectedSubTabIndexes[determinedMainTabIndex] = 0;
    }

    this.groupDataService
      .getAllExperimentsForGroup(this.groupName)
      .pipe(takeUntil(this.destroy$))
      .subscribe((experiments) => (this.experimentDataSource = experiments));
    this.groupDataService
      .getAllRegisteredModelsForGroup(this.groupName)
      .pipe(takeUntil(this.destroy$))
      .subscribe((models) => (this.modelDataSource = models));
    this.groupDataService
      .getAllPromptsForGroup(this.groupName)
      .pipe(takeUntil(this.destroy$))
      .subscribe((prompts) => (this.promptDataSource = prompts));

    if (this.isAdmin) {
      this.experimentRegexDataService
        .getExperimentRegexPermissionsForGroup(this.groupName)
        .pipe(takeUntil(this.destroy$))
        .subscribe((experimentsRegex) => (this.experimentRegexDataSource = experimentsRegex));

      this.modelRegexDataService
        .getModelRegexPermissionsForGroup(this.groupName)
        .pipe(takeUntil(this.destroy$))
        .subscribe((modelsRegex) => (this.modelRegexDataSource = modelsRegex));

      this.promptRegexDataService
        .getPromptRegexPermissionsForGroup(this.groupName)
        .pipe(takeUntil(this.destroy$))
        .subscribe((promptsRegex) => (this.promptRegexDataSource = promptsRegex));
    }
  }

  ngAfterViewInit(): void {
    const mainEntityPath = this.route.parent?.snapshot.url[0]?.path;
    let mainTabIndexToSet = mainEntityPath ? this.tabIndexMapping.indexOf(mainEntityPath) : -1;
    if (mainTabIndexToSet === -1) {
      mainTabIndexToSet = 0; // Default to the first main tab
    }
    // Set the permissionsTabs selectedIndex synchronously so tests without timers can read it
    if (this.permissionsTabs) {
      this.permissionsTabs.selectedIndex = mainTabIndexToSet;
    }
    // After initial setup, disable main tab initialization
    setTimeout(() => {
      this.isMainTabInit = false;
    }, 0);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  openModalAddExperimentPermissionToGroup() {
    this.experimentsDataService
      .getAllExperiments()
      .pipe(
        map((experiments) =>
          experiments.filter((experiment) => !this.experimentDataSource.some((exp) => exp.name === experiment.name))
        ),
        switchMap((experiments) =>
          this.permissionModalService.openGrantPermissionModal(EntityEnum.EXPERIMENT, experiments, this.groupName)
        ),
        filter(Boolean),
        switchMap((newPermission) =>
          this.permissionDataService.addExperimentPermissionToGroup(
            this.groupName,
            newPermission.entity.id,
            newPermission.permission
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Permission granted successfully')),
        switchMap(() => this.groupDataService.getAllExperimentsForGroup(this.groupName))
      )
      .subscribe((experiments) => (this.experimentDataSource = experiments));
  }

  openModalAddModelPermissionToGroup() {
    this.modelDataService
      .getAllModels()
      .pipe(
        map((models) =>
          models
            .filter((model) => !this.modelDataSource.some((m) => m.name === model.name))
            .map((model, index) => ({
              ...model,
              id: `${index}-${model.name}`,
            }))
        ),
        switchMap((models) =>
          this.permissionModalService.openGrantPermissionModal(EntityEnum.MODEL, models, this.groupName)
        ),
        filter(Boolean),
        switchMap((newPermission) =>
          this.permissionDataService.addModelPermissionToGroup(
            newPermission.entity.name,
            this.groupName,
            newPermission.permission
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Permission granted successfully')),
        switchMap(() => this.groupDataService.getAllRegisteredModelsForGroup(this.groupName))
      )
      .subscribe((models) => (this.modelDataSource = models));
  }

  openModalAddPromptPermissionToGroup() {
    this.promptDataService
      .getAllPrompts()
      .pipe(
        map((prompts) =>
          prompts
            .filter((prompt) => !this.promptDataSource.some((p) => p.name === prompt.name))
            .map((prompt, index) => ({
              ...prompt,
              id: `${index}-${prompt.name}`,
            }))
        ),
        switchMap((prompts) =>
          this.permissionModalService.openGrantPermissionModal(EntityEnum.PROMPT, prompts, this.groupName)
        ),
        filter(Boolean),
        switchMap((newPermission) =>
          this.permissionDataService.addPromptPermissionToGroup(
            newPermission.entity.name,
            this.groupName,
            newPermission.permission
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Permission granted successfully')),
        switchMap(() => this.groupDataService.getAllPromptsForGroup(this.groupName))
      )
      .subscribe((prompts) => (this.promptDataSource = prompts));
  }

  handleExperimentActions(event: TableActionEvent<ExperimentModel>) {
    const actionMapping: {
      [key: string]: (experiment: ExperimentModel) => void;
    } = {
      [TableActionEnum.EDIT]: this.handleEditExperimentPermissionForGroup.bind(this),
      [TableActionEnum.REVOKE]: this.revokeExperimentPermissionForGroup.bind(this),
    };

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }

  handleEditExperimentPermissionForGroup(experiment: ExperimentModel) {
    this.permissionModalService
      .openEditPermissionsModal(experiment.name, this.groupName, experiment.permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) =>
          this.permissionDataService.updateExperimentPermissionForGroup(this.groupName, experiment.id, permission)
        ),
        tap(() => this.snackBarService.openSnackBar('Permission updated successfully')),
        switchMap(() => this.groupDataService.getAllExperimentsForGroup(this.groupName))
      )
      .subscribe((experiments) => (this.experimentDataSource = experiments));
  }

  revokeExperimentPermissionForGroup(experiment: ExperimentModel) {
    this.permissionDataService
      .removeExperimentPermissionFromGroup(this.groupName, experiment.id)
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.groupDataService.getAllExperimentsForGroup(this.groupName))
      )
      .subscribe((experiments) => (this.experimentDataSource = experiments));
  }

  handleModelActions(event: TableActionEvent<ModelModel>) {
    const actionMapping: { [key: string]: (model: ModelModel) => void } = {
      [TableActionEnum.EDIT]: this.handleEditModelPermissionForGroup.bind(this),
      [TableActionEnum.REVOKE]: this.revokeModelPermissionForGroup.bind(this),
    };

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }

  handleEditModelPermissionForGroup(model: ModelModel) {
    this.permissionModalService
      .openEditPermissionsModal(model.name, this.groupName, model.permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) =>
          this.permissionDataService.updateModelPermissionForGroup(model.name, this.groupName, permission)
        ),
        tap(() => this.snackBarService.openSnackBar('Permission updated successfully')),
        switchMap(() => this.groupDataService.getAllRegisteredModelsForGroup(this.groupName))
      )
      .subscribe((models) => (this.modelDataSource = models));
  }

  revokeModelPermissionForGroup(model: ModelModel) {
    this.permissionDataService
      .removeModelPermissionFromGroup(model.name, this.groupName)
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.groupDataService.getAllRegisteredModelsForGroup(this.groupName))
      )
      .subscribe((models) => (this.modelDataSource = models));
  }

  handlePromptActions(event: TableActionEvent<ModelModel>) {
    const actionMapping: { [key: string]: (model: ModelModel) => void } = {
      [TableActionEnum.EDIT]: this.handleEditPromptPermissionForGroup.bind(this),
      [TableActionEnum.REVOKE]: this.revokePromptPermissionForGroup.bind(this),
    };

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }

  handleEditPromptPermissionForGroup(prompt: ModelModel) {
    this.permissionModalService
      .openEditPermissionsModal(prompt.name, this.groupName, prompt.permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) =>
          this.permissionDataService.updatePromptPermissionForGroup(prompt.name, this.groupName, permission)
        ),
        tap(() => this.snackBarService.openSnackBar('Permission updated successfully')),
        switchMap(() => this.groupDataService.getAllPromptsForGroup(this.groupName))
      )
      .subscribe((prompts) => (this.promptDataSource = prompts));
  }

  revokePromptPermissionForGroup(prompt: ModelModel) {
    this.permissionDataService
      .removePromptPermissionFromGroup(prompt.name, this.groupName)
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.groupDataService.getAllPromptsForGroup(this.groupName))
      )
      .subscribe((prompts) => (this.promptDataSource = prompts));
  }

  handleTabSelection(index: number) {
    if (this.isMainTabInit) {
      return;
    }
    const groupId = this.route.snapshot.paramMap.get('id');
    this.router.navigate([`/manage/group/${groupId}/${this.tabIndexMapping[index]}/permissions`]);
  }

  handleSubTabSelection(index: number): void {
    if (this.navigating) {
      return;
    }
    const mainIndex = this.permissionsTabs?.selectedIndex;
    // If mainIndex is null or invalid, do not navigate
    if (mainIndex == null || mainIndex < 0 || mainIndex >= this.tabIndexMapping.length) {
      return;
    }
    this.navigating = true;
    const entity = mainIndex !== null && mainIndex >= 0 ? this.tabIndexMapping[mainIndex] : '';
    const subRoute = index === 1 ? AdminPageRoutesEnum.REGEX : AdminPageRoutesEnum.PERMISSIONS;

    this.selectedSubTabIndexes[mainIndex] = index;

    const groupId = this.route.snapshot.paramMap.get('id');
    this.router.navigate([`/manage/group/${groupId}/${entity}/${subRoute}`]).then(() => {
      setTimeout(() => {
        this.navigating = false;
      }, 100);
    });
  }

  // Regex handlers
  openModalAddExperimentRegexPermissionToGroup() {
    const modalData: ManageRegexModalData = {
      regex: '',
      permission: PermissionEnum.READ,
      priority: 100,
    };

    this.dialog
      .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
        data: modalData,
        width: '500px',
      })
      .afterClosed()
      .pipe(
        filter((result): result is ManageRegexModalData => !!result),
        switchMap((result) =>
          this.experimentRegexDataService.addExperimentRegexPermissionToGroup(
            this.groupName,
            result.regex,
            result.permission,
            result.priority
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Experiment regex permission added successfully')),
        switchMap(() => this.experimentRegexDataService.getExperimentRegexPermissionsForGroup(this.groupName))
      )
      .subscribe((data) => (this.experimentRegexDataSource = data));
  }

  handleExperimentRegexActions(event: TableActionEvent<ExperimentRegexPermissionModel>) {
    const item = event.item;
    if (event.action.action === TableActionEnum.EDIT) {
      const modalData: ManageRegexModalData = {
        regex: item.regex,
        permission: item.permission as PermissionEnum,
        priority: item.priority,
      };

      this.dialog
        .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
          data: modalData,
          width: '500px',
        })
        .afterClosed()
        .pipe(
          filter((result): result is ManageRegexModalData => !!result),
          switchMap((result) =>
            this.experimentRegexDataService.updateExperimentRegexPermissionForGroup(
              this.groupName,
              item.regex,
              result.permission,
              result.priority,
              item.id
            )
          ),
          tap(() => this.snackBarService.openSnackBar('Experiment regex permission updated successfully')),
          switchMap(() => this.experimentRegexDataService.getExperimentRegexPermissionsForGroup(this.groupName))
        )
        .subscribe((data) => (this.experimentRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.experimentRegexDataService
        .removeExperimentRegexPermissionFromGroup(this.groupName, event.item.id)
        .pipe(switchMap(() => this.experimentRegexDataService.getExperimentRegexPermissionsForGroup(this.groupName)))
        .subscribe((data) => (this.experimentRegexDataSource = data));
    }
  }

  openModalAddModelRegexPermissionToGroup() {
    const modalData: ManageRegexModalData = {
      regex: '',
      permission: PermissionEnum.READ,
      priority: 100,
    };

    this.dialog
      .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
        data: modalData,
        width: '500px',
      })
      .afterClosed()
      .pipe(
        filter((result): result is ManageRegexModalData => !!result),
        switchMap((result) =>
          this.modelRegexDataService.addModelRegexPermissionToGroup(
            this.groupName,
            result.regex,
            result.permission,
            result.priority
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Model regex permission added successfully')),
        switchMap(() => this.modelRegexDataService.getModelRegexPermissionsForGroup(this.groupName))
      )
      .subscribe((data) => (this.modelRegexDataSource = data));
  }

  openModalAddPromptRegexPermissionToGroup() {
    const modalData: ManageRegexModalData = {
      regex: '',
      permission: PermissionEnum.READ,
      priority: 100,
    };

    this.dialog
      .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
        data: modalData,
        width: '500px',
      })
      .afterClosed()
      .pipe(
        filter((result): result is ManageRegexModalData => !!result),
        switchMap((result) =>
          this.promptRegexDataService.addPromptRegexPermissionToGroup(
            this.groupName,
            result.regex,
            result.permission,
            result.priority
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Prompt regex permission added successfully')),
        switchMap(() => this.promptRegexDataService.getPromptRegexPermissionsForGroup(this.groupName))
      )
      .subscribe((data) => (this.promptRegexDataSource = data));
  }

  handleModelRegexActions(event: TableActionEvent<ModelRegexPermissionModel>) {
    const item = event.item;
    if (event.action.action === TableActionEnum.EDIT) {
      const modalData: ManageRegexModalData = {
        regex: item.regex,
        permission: item.permission as PermissionEnum,
        priority: item.priority,
      };
      this.dialog
        .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
          data: modalData,
          width: '500px',
        })
        .afterClosed()
        .pipe(
          filter((result): result is ManageRegexModalData => !!result),
          switchMap((result) =>
            this.modelRegexDataService.updateModelRegexPermissionForGroup(
              this.groupName,
              item.regex,
              result.permission,
              result.priority,
              item.id
            )
          ),
          tap(() => this.snackBarService.openSnackBar('Model regex permission updated successfully')),
          switchMap(() => this.modelRegexDataService.getModelRegexPermissionsForGroup(this.groupName))
        )
        .subscribe((data) => (this.modelRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.modelRegexDataService
        .removeModelRegexPermissionFromGroup(this.groupName, event.item.id)
        .pipe(switchMap(() => this.modelRegexDataService.getModelRegexPermissionsForGroup(this.groupName)))
        .subscribe((data) => (this.modelRegexDataSource = data));
    }
  }

  handlePromptRegexActions(event: TableActionEvent<PromptRegexPermissionModel>) {
    const item = event.item;
    if (event.action.action === TableActionEnum.EDIT) {
      const modalData: ManageRegexModalData = {
        regex: item.regex,
        permission: item.permission as PermissionEnum,
        priority: item.priority,
      };
      this.dialog
        .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
          data: modalData,
          width: '500px',
        })
        .afterClosed()
        .pipe(
          filter((result): result is ManageRegexModalData => !!result),
          switchMap((result) =>
            this.promptRegexDataService.updatePromptRegexPermissionForGroup(
              this.groupName,
              item.regex,
              result.permission,
              result.priority,
              item.id
            )
          ),
          tap(() => this.snackBarService.openSnackBar('Prompt regex permission updated successfully')),
          switchMap(() => this.promptRegexDataService.getPromptRegexPermissionsForGroup(this.groupName))
        )
        .subscribe((data) => (this.promptRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.promptRegexDataService
        .removePromptRegexPermissionFromGroup(this.groupName, event.item.id)
        .pipe(switchMap(() => this.promptRegexDataService.getPromptRegexPermissionsForGroup(this.groupName)))
        .subscribe((data) => (this.promptRegexDataSource = data));
    }
  }
}
