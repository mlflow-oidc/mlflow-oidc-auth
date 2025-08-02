import { Component, Input, OnInit } from '@angular/core';
import { NavigationUrlService } from '../../services/navigation-url.service';
import { API_URL } from '../../../core/configs/api-urls';

@Component({
  selector: 'ml-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
  standalone: false,
})
export class HeaderComponent implements OnInit {
  @Input() name: string = '';
  @Input() admin: boolean = false;

  constructor(private navigationUrlService: NavigationUrlService) { }

  ngOnInit(): void { }

  redirectToMLflow() {
    // Navigate to MLflow root with proper proxy path handling
    this.navigationUrlService.navigateTo(API_URL.HOME);
  }

  logout() {
    // Use the navigation service with API_URL constant for consistency
    this.navigationUrlService.navigateTo(API_URL.LOGOUT);
  }
}
