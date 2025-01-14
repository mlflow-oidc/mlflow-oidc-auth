import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { HomePageComponent } from './components/home-page/home-page.component';

const routes: Routes = [
  { path: 'experiments', component: HomePageComponent, data: { breadcrumb: 'Experiments' }, },
  { path: 'models', component: HomePageComponent, data: { breadcrumb: 'Models' }, },
  { path: '**', redirectTo: 'experiments' },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class HomePageRoutingModule { }
