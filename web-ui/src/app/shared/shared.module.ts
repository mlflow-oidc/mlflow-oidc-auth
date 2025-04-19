import { NgModule } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
  AccessKeyModalComponent,
  ConfirmModalComponent,
  CreateServiceAccountModalComponent,
  EditPermissionsModalComponent,
  GrantPermissionModalComponent,
  GrantUserPermissionsComponent,
  HeaderComponent,
  TableComponent,
} from "./components";
import { MaterialModule } from "./material/material.module";
import { FormsModule, ReactiveFormsModule } from "@angular/forms";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { NgbModule } from "@ng-bootstrap/ng-bootstrap";
import { RouterLink, RouterLinkWithHref } from "@angular/router";
import { HttpClientModule } from "@angular/common/http";
import { BreadcrumbModule } from "xng-breadcrumb";

const SHARED_COMPONENTS = [
  AccessKeyModalComponent,
  ConfirmModalComponent,
  CreateServiceAccountModalComponent,
  EditPermissionsModalComponent,
  GrantPermissionModalComponent,
  GrantUserPermissionsComponent,
  HeaderComponent,
  TableComponent,
];

@NgModule({
  declarations: [...SHARED_COMPONENTS],
  exports: [...SHARED_COMPONENTS, MaterialModule, BreadcrumbModule],
  imports: [
    MaterialModule,
    CommonModule,
    FormsModule,
    NgbModule,
    RouterLinkWithHref,
    HttpClientModule,
    ReactiveFormsModule,
    MatCheckboxModule,
    RouterLink,
    BreadcrumbModule,
  ],
})
export class SharedModule {}
