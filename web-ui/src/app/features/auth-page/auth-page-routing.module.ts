import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AuthPageComponent } from './components';
import { AuthConfigResolver } from '../../core/resolvers/auth-config.resolver';

const routes: Routes = [
  {
    path: '',
    component: AuthPageComponent,
    resolve: {
      config: AuthConfigResolver
    }
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class AuthPageRoutingModule {}
