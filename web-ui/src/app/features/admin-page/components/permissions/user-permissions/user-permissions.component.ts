import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs';

import { UserDataService } from 'src/app/shared/services';
import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { USER_ACTIONS, USER_COLUMN_CONFIG } from './user-permissions.config';
import { AdminPageRoutesEnum } from '../../../config';

interface UserModel {
  user: string,
}

@Component({
  selector: 'ml-user-permissions',
  templateUrl: './user-permissions.component.html',
  styleUrls: ['./user-permissions.component.scss'],
  standalone: false
})
export class UserPermissionsComponent implements OnInit {
  columnConfig = USER_COLUMN_CONFIG;
  actions: TableActionModel[] = USER_ACTIONS;
  dataSource: UserModel[] = [];

  isLoading = false;

  constructor(
    private readonly router: Router,
    private readonly route: ActivatedRoute,
    private readonly userDataService: UserDataService,
  ) {
  }

  ngOnInit(): void {
    this.isLoading = true;
    this.userDataService.getAllUsers()
      .pipe(
        finalize(() => this.isLoading = false),
      )
      .subscribe(({ users }) => this.dataSource = users.map((user) => ({ user })))
  }

  handleItemAction({ action, item }: TableActionEvent<UserModel>) {
    const actionHandlers: { [key: string]: (user: UserModel) => void } = {
      [TableActionEnum.EDIT]: this.handleUserEdit.bind(this),
    }

    const selectedAction = actionHandlers[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  handleUserEdit({ user }: UserModel): void {
    this.router.navigate([`../${AdminPageRoutesEnum.USER}/` + user], { relativeTo: this.route })
  }
}
