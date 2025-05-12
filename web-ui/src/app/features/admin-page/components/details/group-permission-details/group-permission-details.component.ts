import { Component, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { filter, map, switchMap, tap } from 'rxjs';

import { MatTabGroup } from '@angular/material/tabs';
import { EntityEnum } from 'src/app/core/configs/core';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import {
  TableActionEvent,
  TableActionModel,
  TableColumnConfigModel,
} from 'src/app/shared/components/table/table.interface';
import { ExperimentModel, ModelModel, ExperimentRegexPermissionModel } from 'src/app/shared/interfaces/groups-data.interface';
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

@Component({
  selector: 'ml-group-permission-details',
  templateUrl: './group-permission-details.component.html',
  styleUrls: ['./group-permission-details.component.scss'],
  standalone: false,
})
export class GroupPermissionDetailsComponent implements OnInit {
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
  modelRegexDataSource: any[] = [];
  modelRegexActions = MODELS_REGEX_ACTIONS;

  promptRegexColumnConfig = PROMPTS_REGEX_COLUMN_CONFIG;
  promptRegexDataSource: any[] = [];
  promptRegexActions = PROMPTS_REGEX_ACTIONS;

  @ViewChild('permissionsTabs') permissionsTabs!: MatTabGroup;

  private readonly tabIndexMapping: string[] = ['experiments', 'models', 'prompts'];

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
    private readonly authService: AuthService
  ) {}

  ngOnInit(): void {
    this.groupName = this.route.snapshot.paramMap.get('id') ?? '';

    // set admin flag
    this.isAdmin = this.authService.getUserInfo().is_admin;

    this.groupDataService
      .getAllExperimentsForGroup(this.groupName)
      .subscribe((experiments) => (this.experimentDataSource = experiments));
    this.groupDataService
      .getAllRegisteredModelsForGroup(this.groupName)
      .subscribe((models) => (this.modelDataSource = models));
    this.groupDataService
      .getAllPromptsForGroup(this.groupName)
      .subscribe((prompts) => (this.promptDataSource = prompts));

    // fetch regex permissions for group if admin
    if (this.isAdmin) {
      this.experimentRegexDataService.
        getExperimentRegexPermissionsForGroup(this.groupName)
        .subscribe((experimentsRegex) => (this.experimentRegexDataSource = experimentsRegex));

      this.modelRegexDataService
        .getModelRegexPermissionsForGroup(this.groupName)
        .subscribe((modelsRegex) => (this.modelRegexDataSource = modelsRegex));

        this.promptRegexDataService
        .getPromptRegexPermissionsForGroup(this.groupName)
        .subscribe((promptsRegex) => (this.promptRegexDataSource = promptsRegex));
    }
  }

  ngAfterViewInit(): void {
    const routePath = String(this.route.snapshot.url[2]);
    this.permissionsTabs.selectedIndex = routePath ? this.tabIndexMapping.indexOf(routePath) : 0;
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
    this.router.navigate([`../${this.tabIndexMapping[index]}`], {
      relativeTo: this.route,
    });
  }

  // Regex handlers
  openModalAddExperimentRegexPermissionToGroup() {
    const pattern = window.prompt('Enter regex pattern for experiments');
    if (!pattern) { return; }
    this.permissionModalService
      .openEditPermissionsModal(pattern, this.groupName, PermissionEnum.READ)
      .pipe(
        filter((perm): perm is PermissionEnum => perm != null),
        switchMap((permission) =>
          this.experimentRegexDataService.addExperimentRegexPermissionToGroup(
            this.groupName,
            pattern,
            permission
          )
        ),
        switchMap(() =>
          this.experimentRegexDataService.getExperimentRegexPermissionsForGroup(this.groupName)
        )
      )
      .subscribe((data) => (this.experimentRegexDataSource = data));
  }

  handleExperimentRegexActions(event: TableActionEvent<any>) {
    if (event.action.action === TableActionEnum.EDIT) {
      const item = event.item;
      const newPattern = window.prompt('Update regex pattern', item.pattern);
      if (!newPattern) { return; }
      this.permissionModalService
        .openEditPermissionsModal(item.pattern, this.groupName, item.permission)
        .pipe(
          filter((perm): perm is PermissionEnum => perm != null),
          switchMap((permission) =>
            this.experimentRegexDataService.updateExperimentRegexPermissionForGroup(
              this.groupName,
              item.id,
              newPattern,
              permission
            )
          ),
          switchMap(() =>
            this.experimentRegexDataService.getExperimentRegexPermissionsForGroup(this.groupName)
          )
        )
        .subscribe((data) => (this.experimentRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.experimentRegexDataService
        .removeExperimentRegexPermissionFromGroup(this.groupName, event.item.id)
        .pipe(
          switchMap(() =>
            this.experimentRegexDataService.getExperimentRegexPermissionsForGroup(this.groupName)
          )
        )
        .subscribe((data) => (this.experimentRegexDataSource = data));
    }
  }

  openModalAddModelRegexPermissionToGroup() {
    const pattern = window.prompt('Enter regex pattern for models');
    if (!pattern) { return; }
    this.permissionModalService
      .openEditPermissionsModal(pattern, this.groupName, PermissionEnum.READ)
      .pipe(
        filter((perm): perm is PermissionEnum => perm != null),
        switchMap((permission) =>
          this.modelRegexDataService.addModelRegexPermissionToGroup(
            this.groupName,
            pattern,
            permission
          )
        ),
        switchMap(() =>
          this.modelRegexDataService.getModelRegexPermissionsForGroup(this.groupName)
        )
      )
      .subscribe((data) => (this.modelRegexDataSource = data));
  }

  openModalAddPromptRegexPermissionToGroup() {
    const pattern = window.prompt('Enter regex pattern for prompts');
    if (!pattern) { return; }
    this.permissionModalService
      .openEditPermissionsModal(pattern, this.groupName, PermissionEnum.READ)
      .pipe(
        filter((perm): perm is PermissionEnum => perm != null),
        switchMap((permission) =>
          this.promptRegexDataService.addPromptRegexPermissionToGroup(
            this.groupName,
            pattern,
            permission
          )
        ),
        switchMap(() =>
          this.promptRegexDataService.getPromptRegexPermissionsForGroup(this.groupName)
        )
      )
      .subscribe((data) => (this.promptRegexDataSource = data));
  }

  handleModelRegexActions(event: TableActionEvent<any>) {
    if (event.action.action === TableActionEnum.EDIT) {
      const item = event.item;
      const newPattern = window.prompt('Update regex pattern', item.pattern);
      if (!newPattern) { return; }
      this.permissionModalService
        .openEditPermissionsModal(item.pattern, this.groupName, item.permission)
        .pipe(
          filter((perm): perm is PermissionEnum => perm != null),
          switchMap((permission) =>
            this.modelRegexDataService.updateModelRegexPermissionForGroup(
              this.groupName,
              item.id,
              newPattern,
              permission
            )
          ),
          switchMap(() =>
            this.modelRegexDataService.getModelRegexPermissionsForGroup(this.groupName)
          )
        )
        .subscribe((data) => (this.modelRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.modelRegexDataService
        .removeModelRegexPermissionFromGroup(this.groupName, event.item.id)
        .pipe(
          switchMap(() =>
            this.modelRegexDataService.getModelRegexPermissionsForGroup(this.groupName)
          )
        )
        .subscribe((data) => (this.modelRegexDataSource = data));
    }
  }

  handlePromptRegexActions(event: TableActionEvent<any>) {
    if (event.action.action === TableActionEnum.EDIT) {
      const item = event.item;
      const newPattern = window.prompt('Update regex pattern', item.pattern);
      if (!newPattern) { return; }
      this.permissionModalService
        .openEditPermissionsModal(item.pattern, this.groupName, item.permission)
        .pipe(
          filter((perm): perm is PermissionEnum => perm != null),
          switchMap((permission) =>
            this.promptRegexDataService.updatePromptRegexPermissionForGroup(
              this.groupName,
              item.id,
              newPattern,
              permission
            )
          ),
          switchMap(() =>
            this.promptRegexDataService.getPromptRegexPermissionsForGroup(this.groupName)
          )
        )
        .subscribe((data) => (this.promptRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.promptRegexDataService
        .removePromptRegexPermissionFromGroup(this.groupName, event.item.id)
        .pipe(
          switchMap(() =>
            this.promptRegexDataService.getPromptRegexPermissionsForGroup(this.groupName)
          )
        )
        .subscribe((data) => (this.promptRegexDataSource = data));
    }
  }
}
