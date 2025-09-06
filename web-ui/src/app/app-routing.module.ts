import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { RoutePath } from './core/configs/core';
import { AuthGuard } from './core/guards/auth.guard';

const routes: Routes = [
  {
    path: RoutePath.Auth,
    loadChildren: () => import('./features/auth-page/auth-page.module').then((m) => m.AuthPageModule),
    data: {
      breadcrumb: {
        skip: true,
      },
    },
  },
  {
    path: RoutePath.Home,
    loadChildren: () => import('./features/home-page/home-page.module').then((m) => m.HomePageModule),
    canActivate: [AuthGuard],
    data: {
      breadcrumb: {
        skip: true,
      },
    },
  },
  {
    path: RoutePath.Manage,
    loadChildren: () => import('./features/admin-page/admin-page.module').then((m) => m.AdminPageModule),
    canActivate: [AuthGuard],
  },
  { path: '**', redirectTo: RoutePath.Home },
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { useHash: true })],
  exports: [RouterModule],
})
export class AppRoutingModule {}
