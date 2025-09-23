import { Injectable } from '@angular/core';
import { Resolve } from '@angular/router';
import { Observable } from 'rxjs';
import { RuntimeConfigService } from '../services/runtime-config.service';
import { RuntimeConfig } from '../models/runtime-config.interface';

@Injectable({
  providedIn: 'root'
})
export class AuthConfigResolver implements Resolve<RuntimeConfig> {
  constructor(private runtimeConfigService: RuntimeConfigService) {}

  resolve(): Observable<RuntimeConfig> | Promise<RuntimeConfig> | RuntimeConfig {
    return this.runtimeConfigService.getCurrentConfig();
  }
}
