import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { filter, map, switchMap, tap } from 'rxjs';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { GrantUserPermissionsComponent, GrantUserPermissionsModel } from 'src/app/shared/components';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import {
  ExperimentsDataService,
  PermissionDataService,
  SnackBarService,
  UserDataService,
} from 'src/app/shared/services';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service';
import { COLUMN_CONFIG, TABLE_ACTIONS } from './experiment-permission-details.config';
import { EntityEnum } from 'src/app/core/configs/core';

interface ExperimentModel {
  permission: PermissionEnum;
  username: string;
}

@Component({
  selector: 'ml-experiment-permission-details',
  templateUrl: './experiment-permission-details.component.html',
  styleUrls: ['./experiment-permission-details.component.scss'],
  standalone: false,
})
export class ExperimentPermissionDetailsComponent implements OnInit {
  experimentId!: string;
  userColumnConfig = COLUMN_CONFIG;
  actions: TableActionModel[] = TABLE_ACTIONS;
  userDataSource: ExperimentModel[] = [];

  constructor(
    private readonly experimentDataService: ExperimentsDataService,
    private readonly permissionDataService: PermissionDataService,
    private readonly userDataService: UserDataService,
    private readonly route: ActivatedRoute,
    private readonly permissionModalService: PermissionModalService,
    private readonly snackBarService: SnackBarService
  ) {}

  ngOnInit(): void {
    this.experimentId = this.route.snapshot.paramMap.get('id') ?? '';

    this.experimentDataService
      .getUsersForExperiment(this.experimentId)
      .subscribe((users) => (this.userDataSource = users));
  }

  handleUserEdit(event: ExperimentModel) {
    this.permissionModalService
      .openEditPermissionsModal(this.experimentId, event.username, event.permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) =>
          this.permissionDataService.updateExperimentPermission({
            experiment_id: this.experimentId,
            permission,
            username: event.username,
          })
        ),
        tap(() => this.snackBarService.openSnackBar('Permissions updated successfully')),
        switchMap(() => this.experimentDataService.getUsersForExperiment(this.experimentId))
      )
      .subscribe((users) => {
        this.userDataSource = users;
      });
  }

  handleActions($event: TableActionEvent<ExperimentModel>) {
    const actionMapping: {
      [key: string]: (event: ExperimentModel) => void;
    } = {
      [TableActionEnum.EDIT]: this.handleUserEdit.bind(this),
      [TableActionEnum.REVOKE]: this.revokePermissionForUser.bind(this),
    };

    const selectedAction = actionMapping[$event.action.action];
    if (selectedAction) {
      selectedAction($event.item);
    }
  }

  revokePermissionForUser(item: ExperimentModel) {
    this.permissionDataService
      .deleteExperimentPermission({
        experiment_id: this.experimentId,
        username: item.username,
      })
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.loadUsersForExperiment(this.experimentId))
      )
      .subscribe((users) => (this.userDataSource = users));
  }

  private handleAddEntity(users: string[], entity: EntityEnum) {
    const filteredUsers = users.filter((user: string) => !this.userDataSource.some((u) => u.username === user));
    this.permissionModalService
      .openGrantPermissionModal(
        entity,
        filteredUsers.map((user, index) => ({
          id: `${index}-${user}`,
          name: user,
        })),
        this.experimentId
      )
      .pipe(
        filter(Boolean),
        switchMap(({ entity, permission }) =>
          this.permissionDataService.createExperimentPermission({
            experiment_id: this.experimentId,
            permission: permission,
            username: entity.name,
          })
        ),
        switchMap(() => this.loadUsersForExperiment(this.experimentId))
      )
      .subscribe((users: ExperimentModel[]) => {
        this.userDataSource = users;
      });
  }

  addUser() {
    this.userDataService
      .getAllUsers()
      .pipe(map(({ users }) => users))
      .subscribe((users: string[]) => this.handleAddEntity(users, EntityEnum.USER));
  }

  addServiceAccount() {
    this.userDataService
      .getAllServiceUsers()
      .pipe(map(({ users }) => users))
      .subscribe((users: string[]) => this.handleAddEntity(users, EntityEnum.SERVICE_ACCOUNT));
  }

  loadUsersForExperiment(experimentId: string) {
    return this.experimentDataService.getUsersForExperiment(experimentId);
  }
}
