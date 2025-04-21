import { TestBed } from '@angular/core/testing';
import { jest } from '@jest/globals';
import { MatDialog } from '@angular/material/dialog';
import { of } from 'rxjs';

import { PermissionModalService } from '../permission-modal.service';
import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { EditPermissionsModalComponent, GrantPermissionModalComponent } from '../../components';
import { WithNameAndId } from 'src/app/shared/components/modals/grant-permission-modal/grant-permission-modal.interface';

describe('PermissionModalService', () => {
  let service: PermissionModalService;
  let dialogSpy: jest.Mocked<MatDialog>;

  beforeEach(() => {
    dialogSpy = { open: jest.fn() } as unknown as jest.Mocked<MatDialog>;
    TestBed.configureTestingModule({
      providers: [PermissionModalService, { provide: MatDialog, useValue: dialogSpy }],
    });
    service = TestBed.inject(PermissionModalService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should open EditPermissionsModal with correct data', () => {
    const mockDialogRef = { afterClosed: jest.fn(() => of({})) };
    dialogSpy.open.mockReturnValue(mockDialogRef as any);

    const entity = 'user';
    const targetEntity = 'project';
    const currentPermission = PermissionEnum.READ;

    service.openEditPermissionsModal(entity, targetEntity, currentPermission).subscribe();

    expect(dialogSpy.open).toHaveBeenCalledWith(EditPermissionsModalComponent, {
      data: {
        entity,
        targetEntity,
        currentPermission,
      },
    });
  });

  it('should open GrantPermissionModal with correct data', () => {
    const mockDialogRef = { afterClosed: jest.fn(() => of({})) };
    dialogSpy.open.mockReturnValue(mockDialogRef as any);

    const entityType = EntityEnum.EXPERIMENT;
    const entities: WithNameAndId[] = [{ id: '1123', name: 'Experiment 1' }];
    const targetName = 'Target User';

    service.openGrantPermissionModal(entityType, entities, targetName).subscribe();

    expect(dialogSpy.open).toHaveBeenCalledWith(GrantPermissionModalComponent, {
      data: {
        entityType,
        entities,
        targetName,
      },
    });
  });
});
