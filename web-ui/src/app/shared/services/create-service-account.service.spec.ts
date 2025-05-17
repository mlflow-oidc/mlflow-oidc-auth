import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { of } from 'rxjs';
import { CreateServiceAccountService } from './create-service-account.service';
import { CreateServiceAccountModalComponent } from '../components/modals/create-service-account-modal/create-service-account-modal.component';
import {
  CreateServiceAccountModalData,
  CreateServiceAccountModalResult,
} from '../components/modals/create-service-account-modal/create-service-account-modal.interface';

describe('CreateServiceAccountService', () => {
  let service: CreateServiceAccountService;
  let dialog: { open: jest.Mock };

  beforeEach(() => {
    dialog = { open: jest.fn() };
    jest.clearAllMocks();
    TestBed.configureTestingModule({
      providers: [CreateServiceAccountService, { provide: MatDialog, useValue: dialog }],
    });
    service = TestBed.inject(CreateServiceAccountService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should open the modal and return afterClosed observable', () => {
    const data: CreateServiceAccountModalData = {
      title: 'Create',
      username: 'svc',
      display_name: 'svc',
      is_admin: false,
      is_service_account: true,
    };
    const result: CreateServiceAccountModalResult = {
      username: 'svc',
      display_name: 'svc',
      is_admin: false,
      is_service_account: false,
    };
    const afterClosed$ = of(result);
    dialog.open.mockReturnValue({ afterClosed: () => afterClosed$ });

    const obs$ = service.openCreateServiceAccountModal(data);
    let emitted: any;
    obs$.subscribe((v) => (emitted = v));

    expect(dialog.open).toHaveBeenCalledWith(CreateServiceAccountModalComponent, { data });
    expect(emitted).toEqual(result);
  });
});
