import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import {
  ExperimentPermissionDetailsComponent,
  GroupPermissionDetailsComponent,
  ModelPermissionDetailsComponent,
  PermissionsComponent,
  UserPermissionDetailsComponent,
  PromptPermissionDetailsComponent,
} from './components';
import { AdminPageRoutesEnum } from './config';

const getBreadcrumb = (route: string) => {
  const [entity, id] = route.split('/');
  return `${entity} / ${id}`;
};

const routes: Routes = [
  {
    path: `${AdminPageRoutesEnum.USERS}`,
    component: PermissionsComponent,
  },
  {
    path: `${AdminPageRoutesEnum.USER}/:id/experiments`,
    component: UserPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.USER}/:id/models`,
    component: UserPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.USER}/:id/prompts`,
    component: UserPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.USER}/:id`,
    redirectTo: `${AdminPageRoutesEnum.USER}/:id/experiments`,
  },
  {
    path: `${AdminPageRoutesEnum.EXPERIMENTS}`,
    component: PermissionsComponent,
  },
  {
    path: `${AdminPageRoutesEnum.EXPERIMENT}/:id`,
    component: ExperimentPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.MODELS}`,
    component: PermissionsComponent,
  },
  {
    path: `${AdminPageRoutesEnum.MODEL}/:id`,
    component: ModelPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.PROMPTS}`,
    component: PermissionsComponent,
  },
  {
    path: `${AdminPageRoutesEnum.PROMPT}/:id`,
    component: PromptPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.GROUPS}`,
    component: PermissionsComponent,
  },
  {
    path: `${AdminPageRoutesEnum.GROUP}/:id/experiments`,
    component: GroupPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.GROUP}/:id/models`,
    component: GroupPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: `${AdminPageRoutesEnum.GROUP}/:id`,
    pathMatch: 'full',
    redirectTo: `${AdminPageRoutesEnum.GROUP}/:id/experiments`,
  },
  {
    path: `${AdminPageRoutesEnum.GROUP}/:id/prompts`,
    component: GroupPermissionDetailsComponent,
    data: {
      breadcrumb: getBreadcrumb,
    },
  },
  {
    path: '**',
    redirectTo: `${AdminPageRoutesEnum.USERS}`,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class AdminPageRoutingModule {}
