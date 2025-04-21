import { AfterViewInit, Component, OnInit, ViewChild } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatTabGroup } from '@angular/material/tabs';
import { ActivatedRoute, Router } from '@angular/router';

import { AccessKeyModalComponent } from 'src/app/shared/components';
import { AuthService } from 'src/app/shared/services';
import { EXPERIMENTS_COLUMN_CONFIG, MODELS_COLUMN_CONFIG, PROMPTS_COLUMN_CONFIG } from './home-page.config';
import { AccessKeyDialogData } from 'src/app/shared/components/modals/access-key-modal/access-key-modal.interface';
import { UserDataService } from 'src/app/shared/services/data/user-data.service';
import {
  CurrentUserModel,
  ExperimentPermission,
  RegisteredModelPermission,
  PromptPermission,
} from 'src/app/shared/interfaces/user-data.interface';
import { RoutePath } from '../../home-page-routing.module';

@Component({
  selector: 'ml-home-page',
  templateUrl: './home-page.component.html',
  styleUrls: ['./home-page.component.scss'],
  standalone: false,
})
export class HomePageComponent implements OnInit, AfterViewInit {
  currentUserInfo: CurrentUserModel | null = null;
  experimentsColumnConfig = EXPERIMENTS_COLUMN_CONFIG;
  modelsColumnConfig = MODELS_COLUMN_CONFIG;
  promptsColumnConfig = PROMPTS_COLUMN_CONFIG;
  experimentsDataSource: ExperimentPermission[] = [];
  modelsDataSource: RegisteredModelPermission[] = [];
  promptsDataSource: PromptPermission[] = [];

  @ViewChild('userInfoTabs') userInfoTabs!: MatTabGroup;

  private readonly tabIndexMapping: string[] = [RoutePath.Experiments, RoutePath.Models, RoutePath.Prompts];

  constructor(
    private readonly dialog: MatDialog,
    private readonly authService: AuthService,
    private readonly userDataService: UserDataService,
    private readonly router: Router,
    private readonly route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.currentUserInfo = this.authService.getUserInfo();

    if (this.currentUserInfo) {
      const { experiments, models, prompts } = this.currentUserInfo;

      this.modelsDataSource = models;
      this.experimentsDataSource = experiments;
      this.promptsDataSource = prompts;
    }
  }

  ngAfterViewInit(): void {
    this.userInfoTabs.selectedIndex = this.tabIndexMapping.indexOf(this.route.snapshot.url[0].path);
  }

  showAccessKeyModal() {
    this.userDataService.getAccessKey().subscribe(({ token }) => {
      const data = { token };
      this.dialog.open<AccessKeyModalComponent, AccessKeyDialogData>(AccessKeyModalComponent, { data });
    });
  }

  redirectToMLFlow() {
    window.location.href = '/';
  }

  handleTabSelection(index: number) {
    void this.router.navigate([`../${this.tabIndexMapping[index]}`], {
      relativeTo: this.route,
    });
  }
}
