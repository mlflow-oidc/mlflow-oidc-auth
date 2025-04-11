import { NgModule } from "@angular/core";
import { RouterModule, Routes } from "@angular/router";
import { HomePageComponent } from "./components/home-page/home-page.component";

export enum RoutePath {
  Experiments = "experiments",
  Models = "models",
  Prompts = "prompts",
}

const routes: Routes = [
  {
    path: RoutePath.Experiments,
    component: HomePageComponent,
    data: { breadcrumb: "Experiments" },
  },
  {
    path: RoutePath.Models,
    component: HomePageComponent,
    data: { breadcrumb: "Models" },
  },
  {
    path: RoutePath.Prompts,
    component: HomePageComponent,
    data: { breadcrumb: "Prompts" },
  },
  { path: "**", redirectTo: RoutePath.Experiments },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class HomePageRoutingModule {}
