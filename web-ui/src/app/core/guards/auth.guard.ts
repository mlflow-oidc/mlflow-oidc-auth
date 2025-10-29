import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { RuntimeConfigService } from '../services/runtime-config.service';
import { RoutePath } from '../configs/core';

@Injectable({
  providedIn: 'root'
})
export class AuthGuard implements CanActivate {
  constructor(
    private runtimeConfigService: RuntimeConfigService,
    private router: Router
  ) {}

  canActivate(): boolean {
    const config = this.runtimeConfigService.getCurrentConfig();

    if (!config.authenticated) {
      this.router.navigate([RoutePath.Auth], { replaceUrl: true });
      return false;
    }

    return true;
  }
}
