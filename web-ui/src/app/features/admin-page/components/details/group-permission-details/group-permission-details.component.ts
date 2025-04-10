import { Component, OnInit, ViewChild } from "@angular/core";
import { ActivatedRoute, Router } from "@angular/router";
import { filter, map, switchMap, tap } from "rxjs";

import { MatTabGroup } from "@angular/material/tabs";
import { EntityEnum } from "src/app/core/configs/core";
import { TableActionEnum } from "src/app/shared/components/table/table.config";
import {
  TableActionEvent,
  TableActionModel,
  TableColumnConfigModel,
} from "src/app/shared/components/table/table.interface";
import {
  ExperimentModel,
  ModelModel,
} from "src/app/shared/interfaces/groups-data.interface";
import {
  ExperimentsDataService,
  ModelsDataService,
  PermissionDataService,
  PromptsDataService,
  SnackBarService,
} from "src/app/shared/services";
import { GroupDataService } from "src/app/shared/services/data/group-data.service";
import { PermissionModalService } from "src/app/shared/services/permission-modal.service";
import {
  EXPERIMENT_ACTIONS,
  EXPERIMENT_COLUMN_CONFIG,
  MODELS_ACTIONS,
  MODELS_COLUMN_CONFIG,
  PROMPTS_ACTIONS,
  PROMPTS_COLUMN_CONFIG,
} from "./group-permission-details.config";

@Component({
  selector: "ml-group-permission-details",
  templateUrl: "./group-permission-details.component.html",
  styleUrls: ["./group-permission-details.component.scss"],
  standalone: false,
})
export class GroupPermissionDetailsComponent implements OnInit {
  groupName = "";

  experimentColumnConfig: TableColumnConfigModel[] = EXPERIMENT_COLUMN_CONFIG;
  experimentDataSource: ExperimentModel[] = [];
  experimentActions: TableActionModel[] = EXPERIMENT_ACTIONS;

  modelColumnConfig: TableColumnConfigModel[] = MODELS_COLUMN_CONFIG;
  modelDataSource: ModelModel[] = [];
  modelActions: TableActionModel[] = MODELS_ACTIONS;

  promptColumnConfig: TableColumnConfigModel[] = PROMPTS_COLUMN_CONFIG;
  promptDataSource: ModelModel[] = [];
  promptActions: TableActionModel[] = PROMPTS_ACTIONS;

  @ViewChild("permissionsTabs") permissionsTabs!: MatTabGroup;

  private readonly tabIndexMapping: string[] = [
    "experiments",
    "models",
    "prompts",
  ];

  constructor(
    private readonly groupDataService: GroupDataService,
    private readonly route: ActivatedRoute,
    private readonly permissionDataService: PermissionDataService,
    private readonly permissionModalService: PermissionModalService,
    private readonly experimentsDataService: ExperimentsDataService,
    private readonly snackBarService: SnackBarService,
    private readonly modelDataService: ModelsDataService,
    private readonly promptDataService: PromptsDataService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    this.groupName = this.route.snapshot.paramMap.get("id") ?? "";

    this.groupDataService
      .getAllExperimentsForGroup(this.groupName)
      .subscribe((experiments) => (this.experimentDataSource = experiments));
    this.groupDataService
      .getAllRegisteredModelsForGroup(this.groupName)
      .subscribe((models) => (this.modelDataSource = models));
    this.groupDataService
      .getAllPromptsForGroup(this.groupName)
      .subscribe((prompts) => (this.promptDataSource = prompts));
  }

  ngAfterViewInit(): void {
    const routePath = String(this.route.snapshot.url[2]);
    this.permissionsTabs.selectedIndex = routePath
      ? this.tabIndexMapping.indexOf(routePath)
      : 0;
  }

  openModalAddExperimentPermissionToGroup() {
    this.experimentsDataService
      .getAllExperiments()
      .pipe(
        map((experiments) =>
          experiments.filter(
            (experiment) =>
              !this.experimentDataSource.some(
                (exp) => exp.name === experiment.name,
              ),
          ),
        ),
        switchMap((experiments) =>
          this.permissionModalService.openGrantPermissionModal(
            EntityEnum.EXPERIMENT,
            experiments,
            this.groupName,
          ),
        ),
        filter(Boolean),
        switchMap((newPermission) =>
          this.permissionDataService.addExperimentPermissionToGroup(
            this.groupName,
            newPermission.entity.id,
            newPermission.permission,
          ),
        ),
        tap(() =>
          this.snackBarService.openSnackBar("Permission granted successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllExperimentsForGroup(this.groupName),
        ),
      )
      .subscribe((experiments) => (this.experimentDataSource = experiments));
  }

  openModalAddModelPermissionToGroup() {
    this.modelDataService
      .getAllModels()
      .pipe(
        map((models) =>
          models
            .filter(
              (model) =>
                !this.modelDataSource.some((m) => m.name === model.name),
            )
            .map((model, index) => ({
              ...model,
              id: `${index}-${model.name}`,
            })),
        ),
        switchMap((models) =>
          this.permissionModalService.openGrantPermissionModal(
            EntityEnum.MODEL,
            models,
            this.groupName,
          ),
        ),
        filter(Boolean),
        switchMap((newPermission) =>
          this.permissionDataService.addModelPermissionToGroup(
            newPermission.entity.name,
            this.groupName,
            newPermission.permission,
          ),
        ),
        tap(() =>
          this.snackBarService.openSnackBar("Permission granted successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllRegisteredModelsForGroup(this.groupName),
        ),
      )
      .subscribe((models) => (this.modelDataSource = models));
  }

  openModalAddPromptPermissionToGroup() {
    this.promptDataService
      .getAllPrompts()
      .pipe(
        map((prompts) =>
          prompts
            .filter(
              (prompt) =>
                !this.promptDataSource.some((p) => p.name === prompt.name),
            )
            .map((prompt, index) => ({
              ...prompt,
              id: `${index}-${prompt.name}`,
            })),
        ),
        switchMap((prompts) =>
          this.permissionModalService.openGrantPermissionModal(
            EntityEnum.PROMPT,
            prompts,
            this.groupName,
          ),
        ),
        filter(Boolean),
        switchMap((newPermission) =>
          this.permissionDataService.addPromptPermissionToGroup(
            newPermission.entity.name,
            this.groupName,
            newPermission.permission,
          ),
        ),
        tap(() =>
          this.snackBarService.openSnackBar("Permission granted successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllPromptsForGroup(this.groupName),
        ),
      )
      .subscribe((prompts) => (this.promptDataSource = prompts));
  }

  handleExperimentActions(event: TableActionEvent<ExperimentModel>) {
    const actionMapping: {
      [key: string]: (experiment: ExperimentModel) => void;
    } = {
      [TableActionEnum.EDIT]:
        this.handleEditExperimentPermissionForGroup.bind(this),
      [TableActionEnum.REVOKE]:
        this.revokeExperimentPermissionForGroup.bind(this),
    };

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }

  handleEditExperimentPermissionForGroup(experiment: ExperimentModel) {
    this.permissionModalService
      .openEditPermissionsModal(
        experiment.name,
        this.groupName,
        experiment.permission,
      )
      .pipe(
        filter(Boolean),
        switchMap((permission) =>
          this.permissionDataService.updateExperimentPermissionForGroup(
            this.groupName,
            experiment.id,
            permission,
          ),
        ),
        tap(() =>
          this.snackBarService.openSnackBar("Permission updated successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllExperimentsForGroup(this.groupName),
        ),
      )
      .subscribe((experiments) => (this.experimentDataSource = experiments));
  }

  revokeExperimentPermissionForGroup(experiment: ExperimentModel) {
    this.permissionDataService
      .removeExperimentPermissionFromGroup(this.groupName, experiment.id)
      .pipe(
        tap(() =>
          this.snackBarService.openSnackBar("Permission revoked successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllExperimentsForGroup(this.groupName),
        ),
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
          this.permissionDataService.updateModelPermissionForGroup(
            model.name,
            this.groupName,
            permission,
          ),
        ),
        tap(() =>
          this.snackBarService.openSnackBar("Permission updated successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllRegisteredModelsForGroup(this.groupName),
        ),
      )
      .subscribe((models) => (this.modelDataSource = models));
  }

  revokeModelPermissionForGroup(model: ModelModel) {
    this.permissionDataService
      .removeModelPermissionFromGroup(model.name, this.groupName)
      .pipe(
        tap(() =>
          this.snackBarService.openSnackBar("Permission revoked successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllRegisteredModelsForGroup(this.groupName),
        ),
      )
      .subscribe((models) => (this.modelDataSource = models));
  }

  handlePromptActions(event: TableActionEvent<ModelModel>) {
    const actionMapping: { [key: string]: (model: ModelModel) => void } = {
      [TableActionEnum.EDIT]:
        this.handleEditPromptPermissionForGroup.bind(this),
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
          this.permissionDataService.updatePromptPermissionForGroup(
            prompt.name,
            this.groupName,
            permission,
          ),
        ),
        tap(() =>
          this.snackBarService.openSnackBar("Permission updated successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllPromptsForGroup(this.groupName),
        ),
      )
      .subscribe((prompts) => (this.promptDataSource = prompts));
  }

  revokePromptPermissionForGroup(prompt: ModelModel) {
    this.permissionDataService
      .removePromptPermissionFromGroup(prompt.name, this.groupName)
      .pipe(
        tap(() =>
          this.snackBarService.openSnackBar("Permission revoked successfully"),
        ),
        switchMap(() =>
          this.groupDataService.getAllPromptsForGroup(this.groupName),
        ),
      )
      .subscribe((prompts) => (this.promptDataSource = prompts));
  }

  handleTabSelection(index: number) {
    this.router.navigate([`../${this.tabIndexMapping[index]}`], {
      relativeTo: this.route,
    });
  }
}
