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

const getBreadcrumb = (id: string) => {
  return id;
};

const routes: Routes = [
  // List views
  {
    path: AdminPageRoutesEnum.USERS,
    component: PermissionsComponent,
    data: { breadcrumb: 'users' },
  },
  {
    path: AdminPageRoutesEnum.GROUPS,
    component: PermissionsComponent,
    data: { breadcrumb: 'groups' },
  },
  {
    path: AdminPageRoutesEnum.EXPERIMENTS,
    component: PermissionsComponent,
    data: { breadcrumb: 'experiments' },
  },
  {
    path: AdminPageRoutesEnum.MODELS,
    component: PermissionsComponent,
    data: { breadcrumb: 'models' },
  },
  {
    path: AdminPageRoutesEnum.PROMPTS,
    component: PermissionsComponent,
    data: { breadcrumb: 'prompts' },
  },

  {
    path: AdminPageRoutesEnum.USER,
    pathMatch: 'full',
    redirectTo: AdminPageRoutesEnum.USERS,
  },
  {
    path: AdminPageRoutesEnum.MODEL,
    pathMatch: 'full',
    redirectTo: AdminPageRoutesEnum.MODELS,
  },
  {
    path: AdminPageRoutesEnum.GROUP,
    pathMatch: 'full',
    redirectTo: AdminPageRoutesEnum.GROUPS,
  },
  // User-specific nested routes
  {
    path: AdminPageRoutesEnum.USER,
    data: { breadcrumb: 'user' },
    // Component-less route for structure, or add a component with <router-outlet> if needed
    children: [
      {
        path: ':id',
        data: { breadcrumb: getBreadcrumb },
        children: [
          {
            path: 'experiments',
            data: { breadcrumb: 'experiments' },
            children: [
              { path: 'permissions', component: UserPermissionDetailsComponent, data: { breadcrumb: 'permissions' } },
              { path: 'regex', component: UserPermissionDetailsComponent, data: { breadcrumb: 'regex' } },
              { path: '', pathMatch: 'full', redirectTo: 'permissions' },
            ],
          },
          {
            path: 'models',
            data: { breadcrumb: 'models' },
            children: [
              { path: 'permissions', component: UserPermissionDetailsComponent, data: { breadcrumb: 'permissions' } },
              { path: 'regex', component: UserPermissionDetailsComponent, data: { breadcrumb: 'regex' } },
              { path: '', pathMatch: 'full', redirectTo: 'permissions' },
            ],
          },
          {
            path: 'prompts',
            data: { breadcrumb: 'prompts' },
            children: [
              { path: 'permissions', component: UserPermissionDetailsComponent, data: { breadcrumb: 'permissions' } },
              { path: 'regex', component: UserPermissionDetailsComponent, data: { breadcrumb: 'regex' } },
              { path: '', pathMatch: 'full', redirectTo: 'permissions' },
            ],
          },
          { path: '', pathMatch: 'full', redirectTo: 'experiments/permissions' },
        ],
      },
    ],
  },
  // Group-specific nested routes
  {
    path: AdminPageRoutesEnum.GROUP, // e.g., 'group'
    data: { breadcrumb: 'group' },
    children: [
      {
        path: ':id',
        data: { breadcrumb: getBreadcrumb },
        children: [
          {
            path: 'experiments',
            data: { breadcrumb: 'experiments' },
            children: [
              { path: 'permissions', component: GroupPermissionDetailsComponent, data: { breadcrumb: 'permissions' } },
              { path: 'regex', component: GroupPermissionDetailsComponent, data: { breadcrumb: 'regex' } },
              { path: '', pathMatch: 'full', redirectTo: 'permissions' },
            ],
          },
          {
            path: 'models',
            data: { breadcrumb: 'models' },
            children: [
              { path: 'permissions', component: GroupPermissionDetailsComponent, data: { breadcrumb: 'permissions' } },
              { path: 'regex', component: GroupPermissionDetailsComponent, data: { breadcrumb: 'regex' } },
              { path: '', pathMatch: 'full', redirectTo: 'permissions' },
            ],
          },
          {
            path: 'prompts',
            data: { breadcrumb: 'prompts' },
            children: [
              { path: 'permissions', component: GroupPermissionDetailsComponent, data: { breadcrumb: 'permissions' } },
              { path: 'regex', component: GroupPermissionDetailsComponent, data: { breadcrumb: 'regex' } },
              { path: '', pathMatch: 'full', redirectTo: 'permissions' },
            ],
          },
          { path: '', pathMatch: 'full', redirectTo: 'experiments/permissions' }, // Default for 'group/:id'
        ],
      },
    ],
  },

  // Top-level entity details (Experiment, Model, Prompt)
  {
    path: AdminPageRoutesEnum.EXPERIMENT,
    data: { breadcrumb: 'experiment' },
    children: [{ path: ':id', component: ExperimentPermissionDetailsComponent, data: { breadcrumb: getBreadcrumb } }],
  },
  {
    path: AdminPageRoutesEnum.MODEL,
    data: { breadcrumb: 'model' },
    children: [{ path: ':id', component: ModelPermissionDetailsComponent, data: { breadcrumb: getBreadcrumb } }],
  },
  {
    path: AdminPageRoutesEnum.PROMPT,
    data: { breadcrumb: 'prompt' },
    children: [{ path: ':id', component: PromptPermissionDetailsComponent, data: { breadcrumb: getBreadcrumb } }],
  },

  // Fallback route
  {
    path: '**',
    redirectTo: AdminPageRoutesEnum.USERS,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class AdminPageRoutingModule {}
