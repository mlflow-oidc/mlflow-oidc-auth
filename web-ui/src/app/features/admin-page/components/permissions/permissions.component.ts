import { AfterViewInit, Component, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { MatTabGroup } from '@angular/material/tabs';
import { AdminPageRoutesEnum } from '../../config';

@Component({
  selector: 'ml-permissions',
  templateUrl: './permissions.component.html',
  styleUrls: ['./permissions.component.scss'],
  standalone: false,
})
export class PermissionsComponent implements AfterViewInit {
  @ViewChild('permissionsTabs') permissionsTabs!: MatTabGroup;

  private readonly tabIndexMapping: string[] = [
    AdminPageRoutesEnum.USERS,
    AdminPageRoutesEnum.EXPERIMENTS,
    AdminPageRoutesEnum.PROMPTS,
    AdminPageRoutesEnum.MODELS,
    AdminPageRoutesEnum.GROUPS,
  ];

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  ngAfterViewInit(): void {
    const routePath = this.route.snapshot.routeConfig?.path;
    this.permissionsTabs.selectedIndex = routePath ? this.tabIndexMapping.indexOf(routePath) : 0;
  }

  handleTabSelection(index: number) {
    void this.router.navigate([`../${this.tabIndexMapping[index]}`], {
      relativeTo: this.route,
    });
  }
}
