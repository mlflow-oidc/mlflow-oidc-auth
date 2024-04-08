import { Component, OnInit } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { filter, forkJoin, switchMap, tap } from 'rxjs';
import { ActivatedRoute } from '@angular/router';

import { GrantPermissionModalComponent } from 'src/app/shared/components';
import {
  ExperimentsDataService,
  ModelsDataService,
  PermissionDataService,
  SnackBarService,
} from 'src/app/shared/services';
import {
  EXPERIMENT_ACTIONS,
  EXPERIMENT_COLUMN_CONFIG,
  MODEL_ACTIONS,
  MODEL_COLUMN_CONFIG,
} from './user-permission-details.config';
import { EntityEnum } from 'src/app/core/configs/core';
import {
  GrantPermissionModalData,
} from 'src/app/shared/components/modals/grant-permissoin-modal/grant-permission-modal.inteface';
import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';

@Component({
  selector: 'ml-user-permission-details',
  templateUrl: './user-permission-details.component.html',
  styleUrls: ['./user-permission-details.component.scss'],
})
export class UserPermissionDetailsComponent implements OnInit {
  userId: string = '';
  experimentsColumnConfig = EXPERIMENT_COLUMN_CONFIG;
  modelsColumnConfig = MODEL_COLUMN_CONFIG;

  experimentsDataSource: any[] = [];
  modelsDataSource: any[] = [];
  experimentsActions: TableActionModel[] = EXPERIMENT_ACTIONS;
  modelsActions: TableActionModel[] = MODEL_ACTIONS;

  constructor(
    private readonly dialog: MatDialog,
    private readonly expDataService: ExperimentsDataService,
    private readonly modelDataService: ModelsDataService,
    private readonly permissionDataService: PermissionDataService,
    private readonly route: ActivatedRoute,
    private readonly permissionModalService: PermissionModalService,
    private readonly snackBarService: SnackBarService
  ) {
  }

  ngOnInit(): void {
    this.userId = this.route.snapshot.paramMap.get('id') ?? '';

    forkJoin([
      this.expDataService.getExperimentsForUser(this.userId),
      this.modelDataService.getModelsForUser(this.userId),
    ])
      .subscribe(([experiments, models]) => {
        this.experimentsDataSource = experiments;
        this.modelsDataSource = models;
      });

  }

  addModelPermissionToUser() {
    this.modelDataService.getAllModels()
      .pipe(
        switchMap((models) => this.dialog.open<GrantPermissionModalComponent, GrantPermissionModalData>(GrantPermissionModalComponent, {
          data: {
            entityType: EntityEnum.MODEL,
            entities: models.map(({ name }) => name),
            userName: this.userId,
          }
        }).afterClosed()
        ),
        filter(Boolean),
        switchMap(({ entity, permission, user }) => this.permissionDataService.createModelPermission({
          user_name: this.userId,
          model_name: entity,
          new_permission: permission,
        })),
      )
      .subscribe();
  }

  addExperimentPermissionToUser() {
    this.expDataService.getAllExperiments()
      .pipe(
        switchMap((experiments) => this.dialog.open<GrantPermissionModalComponent, GrantPermissionModalData>(GrantPermissionModalComponent, {
          data: {
            entityType: EntityEnum.EXPERIMENT,
            entities: experiments.map(({ name }) => name),
            userName: this.userId,
          }
        }).afterClosed()
        ),
        filter(Boolean),
        switchMap(({ entity, permission, user }) => {
          return this.permissionDataService.createExperimentPermission({
            user_name: this.userId,
            experiment_name: entity,
            new_permission: permission,
          })
        }),
      )
      .subscribe();
  }

  handleExperimentActions(event: TableActionEvent<any>) {
    const actionMapping: { [key: string]: any } = {
      [TableActionEnum.EDIT]: this.handleEditUserPermissionForExperiment.bind(this),
    }

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }


  handleModelActions({ action, item }: TableActionEvent<any>) {
    const actionMapping: { [key: string]: any } = {
      [TableActionEnum.EDIT]: this.handleEditUserPermissionForModel.bind(this),
    }

    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  handleEditUserPermissionForModel({ name, permissions }: any) {
    this.permissionModalService.openEditUserPermissionsForModelModal(name, this.userId, permissions)
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permissions updated successfully')),
        switchMap(() => this.modelDataService.getModelsForUser(this.userId)),
      )
      .subscribe((models) => this.modelsDataSource = models);
  }

  handleEditUserPermissionForExperiment({ id, permissions }: any) {
    this.permissionModalService.openEditUserPermissionsForExperimentModal(id, this.userId, permissions)
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permissions updated successfully')),
        switchMap(() => this.expDataService.getExperimentsForUser(this.userId)),
      )
      .subscribe((experiments) => this.experimentsDataSource = experiments);
  }
}
