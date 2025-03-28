import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { filter, map, switchMap, tap } from 'rxjs';

import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import { PromptsDataService, PermissionDataService, SnackBarService, UserDataService } from 'src/app/shared/services';
import { COLUMN_CONFIG, TABLE_ACTIONS } from './prompt-permission-details.config';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service';
import { EntityEnum } from 'src/app/core/configs/core';
import { PromptUserListModel } from 'src/app/shared/interfaces/prompts-data.interface';

@Component({
  selector: 'ml-prompt-permission-details',
  templateUrl: './prompt-permission-details.component.html',
  styleUrls: ['./prompt-permission-details.component.scss'],
  standalone: false
})
export class PromptPermissionDetailsComponent implements OnInit {
  promptId!: string;
  userDataSource: PromptUserListModel[] = [];

  userColumnConfig = COLUMN_CONFIG;
  actions: TableActionModel[] = TABLE_ACTIONS;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly promptDataService: PromptsDataService,
    private readonly permissionDataService: PermissionDataService,
    private readonly userDataService: UserDataService,
    private readonly snackService: SnackBarService,
    private readonly permissionModalService: PermissionModalService
  ) {
  }

  ngOnInit(): void {
    this.promptId = this.route.snapshot.paramMap.get('id') ?? '';

    this.loadUsersForPrompt(this.promptId)
      .subscribe((users) => this.userDataSource = users);
  }

  revokePermissionForUser(item: PromptUserListModel) {
    this.permissionDataService.deletePromptPermission({ name: this.promptId, user_name: item.username })
      .pipe(
        tap(() => this.snackService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.loadUsersForPrompt(this.promptId)),
      )
      .subscribe((users) => this.userDataSource = users);
  }

  editPermissionForUser({ username, permission }: PromptUserListModel) {
    this.permissionModalService.openEditPermissionsModal(this.promptId, username, permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) => this.permissionDataService.updatePromptPermission({
          name: this.promptId,
          permission,
          user_name: username,
        })),
        tap(() => this.snackService.openSnackBar('Permission updated')),
        switchMap(() => this.loadUsersForPrompt(this.promptId)),
      )
      .subscribe((users) => {
        this.userDataSource = users;
      });
  }

  handleActions({ action, item }: TableActionEvent<PromptUserListModel>) {
    const actionMapping: { [key: string]: (item: PromptUserListModel) => void } = {
      [TableActionEnum.REVOKE]: this.revokePermissionForUser.bind(this),
      [TableActionEnum.EDIT]: this.editPermissionForUser.bind(this),
    };

    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  loadUsersForPrompt(promptId: string) {
    return this.promptDataService.getUsersForPrompt(promptId);
  }

  addUser() {
    this.userDataService.getAllUsers()
      .pipe(
        map(({ users }) => users.filter((user) => !this.userDataSource.some((u) => u.username === user))),
        switchMap((users) => this.permissionModalService.openGrantPermissionModal(
          EntityEnum.MODEL,
          users.map((user, index) => ({ id: index + user, name: user })),
          this.promptId),
        ),
        filter(Boolean),
        switchMap(({ entity, permission }) => this.permissionDataService.createPromptPermission({
          name: this.promptId,
          permission: permission,
          user_name: entity.name,
        })),
        switchMap(() => this.loadUsersForPrompt(this.promptId)),
      )
      .subscribe((users) => {
        this.userDataSource = users;
      });
  }
}
