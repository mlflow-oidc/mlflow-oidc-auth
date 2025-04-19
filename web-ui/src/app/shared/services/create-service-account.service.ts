import { Injectable } from "@angular/core";
import { MatDialog } from "@angular/material/dialog";
import { CreateServiceAccountModalComponent } from "../components/modals/create-service-account-modal/create-service-account-modal.component";
import { CreateServiceAccountModalData, CreateServiceAccountModalResult } from "../components/modals/create-service-account-modal/create-service-account-modal.interface";

@Injectable({
  providedIn: "root",
})
export class CreateServiceAccountService {
  constructor(private readonly dialog: MatDialog) {}

  openCreateServiceAccountModal(data: CreateServiceAccountModalData) {
    return this.dialog
      .open<CreateServiceAccountModalComponent, CreateServiceAccountModalData, CreateServiceAccountModalResult>(
        CreateServiceAccountModalComponent,
        { data }
      )
      .afterClosed();
  }
}
