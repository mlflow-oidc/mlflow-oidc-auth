import { NgModule } from "@angular/core";
import { RouterModule, Routes } from "@angular/router";
import { RoutePath } from "./core/configs/core";

const routes: Routes = [
  {
    path: RoutePath.Home,
    loadChildren: () =>
      import("./features/home-page/home-page.module").then(
        (m) => m.HomePageModule,
      ),
    data: {
      breadcrumb: {
        skip: true,
      },
    },
  },
  {
    path: RoutePath.Manage,
    loadChildren: () =>
      import("./features/admin-page/admin-page.module").then(
        (m) => m.AdminPageModule,
      ),
  },
  { path: "**", redirectTo: RoutePath.Home },
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { useHash: true })],
  exports: [RouterModule],
})
export class AppRoutingModule {}
