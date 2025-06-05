import { Component, OnInit } from '@angular/core';
import { AuthService } from './shared/services';
import { UserDataService } from './shared/services';
import { finalize } from 'rxjs';
import { CurrentUserModel } from './shared/interfaces/user-data.interface';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  standalone: false,
})
export class AppComponent implements OnInit {
  loading = false;
  user!: CurrentUserModel;

  constructor(
    private readonly userDataService: UserDataService,
    private readonly authService: AuthService
  ) {}

  ngOnInit(): void {
    this.loading = false;
    this.userDataService
      .getCurrentUser()
      .pipe(finalize(() => (this.loading = false)))
      .subscribe((userInfo) => {
        this.authService.setUserInfo(userInfo.user);
        this.user = userInfo.user;
      });
  }
}
