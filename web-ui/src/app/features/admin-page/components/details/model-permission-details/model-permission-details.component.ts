import { Component, OnInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { filter, map, switchMap, tap } from "rxjs";

import { EntityEnum } from "src/app/core/configs/core";
import { TableActionEnum } from "src/app/shared/components/table/table.config";
import {
  TableActionEvent,
  TableActionModel,
} from "src/app/shared/components/table/table.interface";
import { ModelUserListModel } from "src/app/shared/interfaces/models-data.interface";
import {
  ModelsDataService,
  PermissionDataService,
  SnackBarService,
  UserDataService,
} from "src/app/shared/services";
import { PermissionModalService } from "src/app/shared/services/permission-modal.service";
import {
  COLUMN_CONFIG,
  TABLE_ACTIONS,
} from "./model-permission-details.config";

@Component({
  selector: "ml-model-permission-details",
  templateUrl: "./model-permission-details.component.html",
  styleUrls: ["./model-permission-details.component.scss"],
  standalone: false,
})
export class ModelPermissionDetailsComponent implements OnInit {
  modelId!: string;
  userDataSource: ModelUserListModel[] = [];

  userColumnConfig = COLUMN_CONFIG;
  actions: TableActionModel[] = TABLE_ACTIONS;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly modelDataService: ModelsDataService,
    private readonly permissionDataService: PermissionDataService,
    private readonly userDataService: UserDataService,
    private readonly snackService: SnackBarService,
    private readonly permissionModalService: PermissionModalService,
  ) { }

  ngOnInit(): void {
    this.modelId = this.route.snapshot.paramMap.get("id") ?? "";

    this.loadUsersForModel(this.modelId).subscribe(
      (users) => (this.userDataSource = users),
    );
  }

  revokePermissionForUser(item: ModelUserListModel) {
    this.permissionDataService
      .deleteModelPermission({ name: this.modelId, username: item.username })
      .pipe(
        tap(() =>
          this.snackService.openSnackBar("Permission revoked successfully"),
        ),
        switchMap(() => this.loadUsersForModel(this.modelId)),
      )
      .subscribe((users) => (this.userDataSource = users));
  }

  editPermissionForUser({ username, permission }: ModelUserListModel) {
    this.permissionModalService
      .openEditPermissionsModal(this.modelId, username, permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) =>
          this.permissionDataService.updateModelPermission({
            name: this.modelId,
            permission,
            username: username,
          }),
        ),
        tap(() => this.snackService.openSnackBar("Permission updated")),
        switchMap(() => this.loadUsersForModel(this.modelId)),
      )
      .subscribe((users) => {
        this.userDataSource = users;
      });
  }

  handleActions({ action, item }: TableActionEvent<ModelUserListModel>) {
    const actionMapping: { [key: string]: (item: ModelUserListModel) => void } =
    {
      [TableActionEnum.REVOKE]: this.revokePermissionForUser.bind(this),
      [TableActionEnum.EDIT]: this.editPermissionForUser.bind(this),
    };

    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  loadUsersForModel(modelId: string) {
    return this.modelDataService.getUsersForModel(modelId);
  }

  private handleAddEntity(users: string[], entity: EntityEnum) {
    const filteredUsers = users.filter(
      (user: string) => !this.userDataSource.some((u) => u.username === user),
    );
    this.permissionModalService.openGrantPermissionModal(
      entity,
      filteredUsers.map((user, index) => ({ id: index + user, name: user })),
      this.modelId,
    )
      .pipe(
        filter(Boolean),
        switchMap(({ entity, permission }) =>
          this.permissionDataService.createModelPermission({
            name: this.modelId,
            permission: permission,
            username: entity.name,
          }),
        ),
        switchMap(() => this.loadUsersForModel(this.modelId)),
      )
      .subscribe((users: ModelUserListModel[]) => {
        this.userDataSource = users;
      });
  }

  addUser() {
    this.userDataService.getAllUsers().pipe(
      map(({ users }) => users),
    ).subscribe((users: string[]) => this.handleAddEntity(users, EntityEnum.USER));
  }

  addServiceAccount() {
    this.userDataService.getAllServiceUsers().pipe(
      map(({ users }) => users),
    ).subscribe((users: string[]) => this.handleAddEntity(users, EntityEnum.SERVICE_ACCOUNT));
  }
}
