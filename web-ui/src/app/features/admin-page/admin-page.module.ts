import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

import {
  AdminPageComponent,
  ExperimentPermissionDetailsComponent,
  ExperimentPermissionsComponent,
  GroupPermissionDetailsComponent,
  GroupPermissionsComponent,
  ModelPermissionDetailsComponent,
  ModelPermissionsComponent,
  PromptPermissionDetailsComponent,
  PromptPermissionsComponent,
  PermissionsComponent,
  UserPermissionDetailsComponent,
  UserPermissionsComponent,
} from './components';
import { AdminPageRoutingModule } from './admin-page-routing.module';
import { SharedModule } from '../../shared/shared.module';


@NgModule({
  declarations: [
    AdminPageComponent,
    UserPermissionsComponent,
    ExperimentPermissionsComponent,
    ModelPermissionsComponent,
    UserPermissionDetailsComponent,
    PermissionsComponent,
    ExperimentPermissionDetailsComponent,
    ModelPermissionDetailsComponent,
    PromptPermissionDetailsComponent,
    PromptPermissionsComponent,
    GroupPermissionDetailsComponent,
    GroupPermissionsComponent,
  ],
  imports: [
    CommonModule,
    SharedModule,
    AdminPageRoutingModule,
    FormsModule,
    RouterModule,
  ],
})
export class AdminPageModule {}
