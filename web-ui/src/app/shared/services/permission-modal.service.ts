import { Injectable } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';

import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { EditPermissionsModalComponent, GrantPermissionModalComponent } from '../components';
import {
  PermissionDialogResultModel,
  PermissionsDialogData,
} from '../components/modals/edit-permissions-modal/edit-permissions-modal.interface';
import {
  GrantPermissionModalData,
  GrantPermissionModalResult,
  WithNameAndId,
} from '../components/modals/grant-permission-modal/grant-permission-modal.interface';

@Injectable({
  providedIn: 'root',
})
export class PermissionModalService {
  constructor(private readonly dialog: MatDialog) {}

  openEditPermissionsModal(entity: string, targetEntity: string, currentPermission: PermissionEnum) {
    const dialogData: PermissionsDialogData = {
      targetEntity,
      entity,
      currentPermission,
    };

    return this.dialog
      .open<
        EditPermissionsModalComponent,
        PermissionsDialogData,
        PermissionDialogResultModel
      >(EditPermissionsModalComponent, { data: dialogData })
      .afterClosed();
  }

  openGrantPermissionModal(entityType = EntityEnum.EXPERIMENT, entities: WithNameAndId[], targetName: string) {
    return this.dialog
      .open<GrantPermissionModalComponent, GrantPermissionModalData, GrantPermissionModalResult>(
        GrantPermissionModalComponent,
        {
          data: {
            entityType,
            entities,
            targetName,
          },
        }
      )
      .afterClosed();
  }
}
