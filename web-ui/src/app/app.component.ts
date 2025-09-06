import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService } from './shared/services';
import { UserDataService } from './shared/services';
import { RuntimeConfigService } from './core/services/runtime-config.service';
import { switchMap, of, EMPTY, delay } from 'rxjs';
import { CurrentUserModel } from './shared/interfaces/user-data.interface';
import { RoutePath } from './core/configs/core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  standalone: false,
})
export class AppComponent implements OnInit {
  loading = true;
  user!: CurrentUserModel;
  isAuthenticated = false;

  constructor(
    private readonly userDataService: UserDataService,
    private readonly authService: AuthService,
    private readonly runtimeConfigService: RuntimeConfigService,
    private readonly router: Router,
    private readonly route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.loading = true;

    // First load the runtime config, then check authentication
    this.runtimeConfigService.loadConfig().pipe(
      switchMap((config) => {
        this.isAuthenticated = config.authenticated;

        // If not authenticated, navigate to auth page, preserving query params if any
        if (!config.authenticated) {
          this.loading = false;

          // Add a small delay to ensure router has finished parsing the URL
          return of(null).pipe(delay(100)).pipe(switchMap(() => {
            const currentUrl = this.router.url;
            const fullUrl = window.location.href;
            const hash = window.location.hash;

            // Check if we're already on the auth page
            const isOnAuthPage = currentUrl.includes(`/${RoutePath.Auth}`) ||
                                currentUrl.includes(`#/${RoutePath.Auth}`) ||
                                currentUrl.startsWith(`/${RoutePath.Auth}`) ||
                                hash.includes(`/${RoutePath.Auth}`);


            if (!isOnAuthPage) {

              // Extract query parameters from hash if they exist
              const hashMatch = hash.match(/#\/auth\?(.+)/);
              const queryParams: any = {};

              if (hashMatch && hashMatch[1]) {
                // Parse query parameters from hash
                const params = new URLSearchParams(hashMatch[1]);
                params.forEach((value, key) => {
                  if (!queryParams[key]) {
                    queryParams[key] = [];
                  }
                  queryParams[key].push(value);
                });
              }

              // Navigate to auth page with preserved query params
              this.router.navigate([RoutePath.Auth], {
                queryParams: Object.keys(queryParams).length > 0 ? queryParams : undefined,
                replaceUrl: true,
                state: { config }
              });
            }

            return EMPTY;
          }));
        }

        // If authenticated, load user data
        return this.userDataService.getCurrentUser();
      })
    ).subscribe({
      next: (userInfo) => {
        if (userInfo) {
          this.authService.setUserInfo(userInfo.user);
          this.user = userInfo.user;
        }
        this.loading = false;
      },
      error: (error) => {
        console.error('Failed to load user data:', error);
        this.loading = false;

        // If user data fails to load, redirect to auth preserving query parameters
        const currentUrl = this.router.url;
        const hash = window.location.hash;
        const isOnAuthPage = currentUrl.includes(`/${RoutePath.Auth}`) ||
                            currentUrl.includes(`#/${RoutePath.Auth}`) ||
                            hash.includes(`/${RoutePath.Auth}`);

        if (!isOnAuthPage) {
          // Extract and preserve query parameters if they exist
          const hashMatch = hash.match(/#\/auth\?(.+)/);
          const queryParams: any = {};

          if (hashMatch && hashMatch[1]) {
            const params = new URLSearchParams(hashMatch[1]);
            params.forEach((value, key) => {
              if (!queryParams[key]) {
                queryParams[key] = [];
              }
              queryParams[key].push(value);
            });
          }

          this.router.navigate([RoutePath.Auth], {
            queryParams: Object.keys(queryParams).length > 0 ? queryParams : undefined,
            replaceUrl: true
          });
        }
      }
    });
  }
}
