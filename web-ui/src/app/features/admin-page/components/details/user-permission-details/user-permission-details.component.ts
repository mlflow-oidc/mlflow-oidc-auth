import { AfterViewInit, Component, OnInit, ViewChild } from "@angular/core";
import { MatTabGroup } from "@angular/material/tabs";
import { ActivatedRoute, Router } from "@angular/router";
import { filter, forkJoin, map, switchMap, tap } from "rxjs";
import { EntityEnum } from "src/app/core/configs/core";
import { PermissionTypeEnum } from "src/app/core/configs/permissions";
import { TableActionEnum } from "src/app/shared/components/table/table.config";
import {
  TableActionEvent,
  TableActionModel,
} from "src/app/shared/components/table/table.interface";
import { ExperimentForUserModel } from "src/app/shared/interfaces/experiments-data.interface";
import { ModelPermissionModel } from "src/app/shared/interfaces/models-data.interface";
import {
  ExperimentsDataService,
  ModelsDataService,
  PermissionDataService,
  SnackBarService,
} from "src/app/shared/services";
import { PermissionModalService } from "src/app/shared/services/permission-modal.service";
import {
  EXPERIMENT_ACTIONS,
  EXPERIMENT_COLUMN_CONFIG,
  MODEL_ACTIONS,
  MODEL_COLUMN_CONFIG,
} from "./user-permission-details.config";

@Component({
  selector: "ml-user-permission-details",
  templateUrl: "./user-permission-details.component.html",
  styleUrls: ["./user-permission-details.component.scss"],
  standalone: false,
})
export class UserPermissionDetailsComponent implements OnInit, AfterViewInit {
  userId: string = "";
  experimentsColumnConfig = EXPERIMENT_COLUMN_CONFIG;
  modelsColumnConfig = MODEL_COLUMN_CONFIG;

  experimentsDataSource: ExperimentForUserModel[] = [];
  modelsDataSource: ModelPermissionModel[] = [];
  experimentsActions: TableActionModel[] = EXPERIMENT_ACTIONS;
  modelsActions: TableActionModel[] = MODEL_ACTIONS;

  @ViewChild("userTabs") permissionsTabs!: MatTabGroup;

  private readonly tabIndexMapping: string[] = ["experiments", "models"];

  constructor(
    private readonly expDataService: ExperimentsDataService,
    private readonly modelDataService: ModelsDataService,
    private readonly permissionDataService: PermissionDataService,
    private readonly route: ActivatedRoute,
    private readonly permissionModalService: PermissionModalService,
    private readonly snackBarService: SnackBarService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    this.userId = this.route.snapshot.paramMap.get("id") ?? "";

    forkJoin([
      this.expDataService.getExperimentsForUser(this.userId),
      this.modelDataService.getModelsForUser(this.userId),
    ]).subscribe(([experiments, models]) => {
      this.experimentsDataSource = experiments;
      this.modelsDataSource = models;
    });
  }

  ngAfterViewInit(): void {
    const routePath = String(this.route.snapshot.url[2]);
    this.permissionsTabs.selectedIndex = routePath
      ? this.tabIndexMapping.indexOf(routePath)
      : 0;
  }

  addModelPermissionToUser() {
    return this.modelDataService
      .getAllModels()
      .pipe(
        map((models) =>
          models.map((model, index) => ({
            ...model,
            id: `${index}-${model.name}`,
          })),
        ),
        map((models) =>
          models.filter(
            (model) =>
              !this.modelsDataSource.some((m) => m.name === model.name),
          ),
        ),
        switchMap((models) =>
          this.permissionModalService.openGrantPermissionModal(
            EntityEnum.MODEL,
            models,
            this.userId,
          ),
        ),
        filter(Boolean),
        switchMap(({ entity, permission }) =>
          this.permissionDataService.createModelPermission({
            username: this.userId,
            name: entity.name,
            permission: permission,
          }),
        ),
        tap(() =>
          this.snackBarService.openSnackBar("Permission granted successfully"),
        ),
        switchMap(() => this.modelDataService.getModelsForUser(this.userId)),
      )
      .subscribe((models) => (this.modelsDataSource = models));
  }

  addExperimentPermissionToUser() {
    this.expDataService
      .getAllExperiments()
      .pipe(
        map((experiments) =>
          experiments.filter(
            (experiment) =>
              !this.experimentsDataSource.some(
                (exp) => exp.id === experiment.id,
              ),
          ),
        ),
        switchMap((experiments) =>
          this.permissionModalService.openGrantPermissionModal(
            EntityEnum.EXPERIMENT,
            experiments,
            this.userId,
          ),
        ),
        filter(Boolean),
        switchMap(({ entity, permission }) => {
          return this.permissionDataService.createExperimentPermission({
            username: this.userId,
            experiment_name: entity.name,
            permission,
          });
        }),
        tap(() =>
          this.snackBarService.openSnackBar("Permission granted successfully"),
        ),
        switchMap(() => this.expDataService.getExperimentsForUser(this.userId)),
      )
      .subscribe((experiments) => (this.experimentsDataSource = experiments));
  }

  handleExperimentActions(event: TableActionEvent<ExperimentForUserModel>) {
    const actionMapping: {
      [key: string]: (experiment: ExperimentForUserModel) => void;
    } = {
      [TableActionEnum.EDIT]:
        this.handleEditUserPermissionForExperiment.bind(this),
      [TableActionEnum.REVOKE]:
        this.revokeExperimentPermissionForUser.bind(this),
    };

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }

  revokeExperimentPermissionForUser(item: {
    id: string;
    type: PermissionTypeEnum;
  }) {
    if (item.type !== PermissionTypeEnum.USER) {
      this.snackBarService.openSnackBar("Nothing to reset");
      return;
    }

    this.permissionDataService
      .deleteExperimentPermission({
        experiment_id: item.id,
        username: this.userId,
      })
      .pipe(
        tap(() =>
          this.snackBarService.openSnackBar("Permission revoked successfully"),
        ),
        switchMap(() => this.expDataService.getExperimentsForUser(this.userId)),
      )
      .subscribe((experiments) => (this.experimentsDataSource = experiments));
  }

  revokeModelPermissionForUser({ name, type }: ModelPermissionModel) {
    if (type !== PermissionTypeEnum.USER) {
      this.snackBarService.openSnackBar("Nothing to reset");
      return;
    }

    this.permissionDataService
      .deleteModelPermission({ name: name, username: this.userId })
      .pipe(
        tap(() =>
          this.snackBarService.openSnackBar("Permission revoked successfully"),
        ),
        switchMap(() => this.modelDataService.getModelsForUser(this.userId)),
      )
      .subscribe((models) => (this.modelsDataSource = models));
  }

  handleModelActions({ action, item }: TableActionEvent<ModelPermissionModel>) {
    const actionMapping: {
      [key: string]: (model: ModelPermissionModel) => void;
    } = {
      [TableActionEnum.EDIT]: this.handleEditUserPermissionForModel.bind(this),
      [TableActionEnum.REVOKE]: this.revokeModelPermissionForUser.bind(this),
    };

    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  handleEditUserPermissionForModel({
    name,
    permission,
    type,
  }: ModelPermissionModel) {
    this.permissionModalService
      .openEditPermissionsModal(name, this.userId, permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) => {
          const permissionData = {
            name,
            permission,
            username: this.userId,
          };

          return type !== PermissionTypeEnum.FALLBACK
            ? this.permissionDataService.createModelPermission(permissionData)
            : this.permissionDataService.updateModelPermission(permissionData);
        }),
        tap(() =>
          this.snackBarService.openSnackBar("Permissions updated successfully"),
        ),
        switchMap(() => this.modelDataService.getModelsForUser(this.userId)),
      )
      .subscribe((models) => (this.modelsDataSource = models));
  }

  handleEditUserPermissionForExperiment({
    id,
    permission,
    type,
  }: ExperimentForUserModel) {
    this.permissionModalService
      .openEditPermissionsModal(id, this.userId, permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) => {
          const permissionData = {
            experiment_id: id,
            permission,
            username: this.userId,
          };
          return type !== PermissionTypeEnum.USER
            ? this.permissionDataService.createExperimentPermission(
                permissionData,
              )
            : this.permissionDataService.updateExperimentPermission(
                permissionData,
              );
        }),
        tap(() =>
          this.snackBarService.openSnackBar("Permissions updated successfully"),
        ),
        switchMap(() => this.expDataService.getExperimentsForUser(this.userId)),
      )
      .subscribe((experiments) => (this.experimentsDataSource = experiments));
  }

  handleTabSelection(index: number) {
    void this.router.navigate([`../${this.tabIndexMapping[index]}`], {
      relativeTo: this.route,
    });
  }
}
