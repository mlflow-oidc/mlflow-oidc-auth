import { Component, OnInit } from '@angular/core';
import { MatLegacyDialog as MatDialog } from '@angular/material/legacy-dialog';
import { AccessKeyModalComponent } from 'src/app/shared/components';
import { AuthService } from 'src/app/shared/services';
import { EXPERIMENTS_COLUMN_CONFIG, MODELS_COLUMN_CONFIG } from './home-page.config';
import { AccessKeyDialogData } from 'src/app/shared/components/modals/access-key-modal/access-key-modal.interface';
import { UserDataService } from 'src/app/shared/services/data/user-data.service';
import {
  CurrentUserModel,
  ExperimentPermission,
  RegisteredModelPermission,
} from 'src/app/shared/interfaces/user-data.interface';

@Component({
  selector: 'ml-home-page',
  templateUrl: './home-page.component.html',
  styleUrls: ['./home-page.component.scss'],
})
export class HomePageComponent implements OnInit {
  currentUserInfo: CurrentUserModel | null = null;
  experimentsColumnConfig = EXPERIMENTS_COLUMN_CONFIG;
  modelsColumnConfig = MODELS_COLUMN_CONFIG;
  experimentsDataSource: ExperimentPermission[] = [];
  modelsDataSource: RegisteredModelPermission[] = [];

  constructor(
    private readonly dialog: MatDialog,
    private readonly authService: AuthService,
    private readonly userDataService: UserDataService,
  ) {
  }

  ngOnInit(): void {
    this.currentUserInfo = this.authService.getUserInfo();

    if (this.currentUserInfo) {
      const { experiments, models } = this.currentUserInfo;

      this.modelsDataSource = models;
      this.experimentsDataSource = experiments;
    }
  }

  showAccessKeyModal() {
    this.userDataService.getAccessKey()
      .subscribe(({ token }) => {
        const data = { token };
        this.dialog.open<AccessKeyModalComponent, AccessKeyDialogData>(AccessKeyModalComponent, { data })
      });
  }

  redirectToMLFlow() {
    window.location.href = '/';
  }
}
