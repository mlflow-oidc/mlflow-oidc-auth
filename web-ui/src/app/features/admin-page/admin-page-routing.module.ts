import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import {
  ExperimentPermissionDetailsComponent,
  GroupPermissionDetailsComponent,
  ModelPermissionDetailsComponent,
  PermissionsComponent,
  UserPermissionDetailsComponent,
} from './components';
import { AdminPageRoutesEnum } from './config';

const getBreadcrumb = (route: string) => {
  const [_, entity, id] = route.split('/');
  return `${entity} / ${id}`;
};

const routes: Routes = [
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.USERS}`,
    component: PermissionsComponent,
    data: {
      breadcrumb: 'Users',
    },
  },
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.USER}/:id`,
    component: UserPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.EXPERIMENTS}`,
    component: PermissionsComponent,
    data: {
      breadcrumb: 'Experiments',
    },
  },
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.EXPERIMENT}/:id`,
    component: ExperimentPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.MODELS}`,
    component: PermissionsComponent,
    data: {
      breadcrumb: 'Models',
    },
  },
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.MODEL}/:id`,
    component: ModelPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.GROUPS}`,
    component: PermissionsComponent,
    data: {
      breadcrumb: 'Groups',
    },
  },
  {
    path: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.GROUP}/:id`,
    component: GroupPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: '**',
    redirectTo: `${AdminPageRoutesEnum.PERMISSIONS}/${AdminPageRoutesEnum.USERS}`,
    pathMatch: 'full',
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class AdminPageRoutingModule {}
