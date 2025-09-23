import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { AuthPageRoutingModule } from './auth-page-routing.module';
import { AuthPageComponent } from './components';

@NgModule({
  declarations: [
    AuthPageComponent
  ],
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    AuthPageRoutingModule
  ]
})
export class AuthPageModule {}
