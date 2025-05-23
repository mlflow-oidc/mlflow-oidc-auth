import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs';

import { UserDataService } from 'src/app/shared/services';
import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { USER_ACTIONS, USER_SERVICE_ACCOUNT_ACTIONS, USER_COLUMN_CONFIG } from './user-permissions.config';
import { AdminPageRoutesEnum } from '../../../config';
import { CreateServiceAccountService } from 'src/app/shared/services/create-service-account.service';
import { UserModel } from 'src/app/shared/interfaces/user-data.interface';
import { MatDialog } from '@angular/material/dialog';
import { AccessKeyModalComponent } from 'src/app/shared/components';
import { AccessKeyDialogData } from 'src/app/shared/components/modals/access-key-modal/access-key-modal.interface';

@Component({
  selector: 'ml-user-permissions',
  templateUrl: './user-permissions.component.html',
  styleUrls: ['./user-permissions.component.scss'],
  standalone: false,
})
export class UserPermissionsComponent implements OnInit {
  columnConfig = USER_COLUMN_CONFIG;
  serviceAccountColumnConfig = USER_COLUMN_CONFIG;
  actions: TableActionModel[] = USER_ACTIONS;
  serviceAccountActions: TableActionModel[] = USER_SERVICE_ACCOUNT_ACTIONS;
  dataSource: UserModel[] = [];
  serviceAccountsDataSource: UserModel[] = [];

  isLoading = false;
  isServiceAccountsLoading = false;

  constructor(
    private readonly router: Router,
    private readonly route: ActivatedRoute,
    private readonly dialog: MatDialog,
    private readonly userDataService: UserDataService,
    private readonly createServiceAccountService: CreateServiceAccountService
  ) {}

  ngOnInit(): void {
    this.isLoading = true;
    this.userDataService
      .getAllUsers()
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe(({ users }) => (this.dataSource = users.map((username) => ({ username }))));
    this.isServiceAccountsLoading = true;
    this.userDataService
      .getAllServiceUsers()
      .pipe(finalize(() => (this.isServiceAccountsLoading = false)))
      .subscribe(
        ({ users }) =>
          (this.serviceAccountsDataSource = users.map((username) => ({
            username,
          })))
      );
  }

  handleItemAction({ action, item }: TableActionEvent<UserModel>) {
    const actionHandlers: { [key: string]: (user: UserModel) => void } = {
      [TableActionEnum.EDIT]: this.handleUserEdit.bind(this),
    };

    const selectedAction = actionHandlers[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  handleServiceAccountAction({ action, item }: TableActionEvent<UserModel>) {
    const actionHandlers: { [key: string]: (user: UserModel) => void } = {
      [TableActionEnum.EDIT]: this.handleUserEdit.bind(this),
      [TableActionEnum.DELETE]: this.handleServiceAccountDelete.bind(this),
      [TableActionEnum.GET_ACCESS_KEY]: this.handleAccessKey.bind(this),
    };
    const selectedAction = actionHandlers[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  handleUserEdit({ username }: UserModel): void {
    this.router.navigate([`../${AdminPageRoutesEnum.USER}/` + username], {
      relativeTo: this.route,
    });
  }

  handleServiceAccountDelete({ username }: UserModel): void {
    this.userDataService.deleteUser({ username }).subscribe(() => {
      this.isServiceAccountsLoading = true;
      this.userDataService
        .getAllServiceUsers()
        .pipe(finalize(() => (this.isServiceAccountsLoading = false)))
        .subscribe(
          ({ users }) =>
            (this.serviceAccountsDataSource = users.map((username) => ({
              username,
            })))
        );
    });
  }

  createServiceAccount(): void {
    this.createServiceAccountService
      .openCreateServiceAccountModal({ title: 'Create Service Account' })
      .subscribe((result) => {
        if (result) {
          this.userDataService.createServiceAccount(result).subscribe(() => {
            this.isServiceAccountsLoading = true;
            this.userDataService
              .getAllServiceUsers()
              .pipe(finalize(() => (this.isServiceAccountsLoading = false)))
              .subscribe(
                ({ users }) =>
                  (this.serviceAccountsDataSource = users.map((username) => ({
                    username,
                  })))
              );
          });
        }
      });
  }

  handleAccessKey({ username }: UserModel): void {
    this.dialog.open<AccessKeyModalComponent, AccessKeyDialogData>(AccessKeyModalComponent, {
      data: { username },
    });
  }
}
