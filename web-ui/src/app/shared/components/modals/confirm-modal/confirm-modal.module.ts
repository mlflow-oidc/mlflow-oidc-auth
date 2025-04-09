import { NgModule } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatDialogModule } from "@angular/material/dialog";
import { ConfirmModalComponent } from "./confirm-modal.component";

@NgModule({
  declarations: [ConfirmModalComponent],
  imports: [CommonModule, MatDialogModule],
  exports: [ConfirmModalComponent],
})
export class ConfirmModalModule {}
