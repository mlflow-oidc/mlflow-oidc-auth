import { Component, Input, OnInit } from '@angular/core';

@Component({
  selector: 'ml-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
  standalone: false
})
export class HeaderComponent implements OnInit {
  @Input() name: string = '';
  @Input() admin: boolean = false;

  constructor() { }

  ngOnInit(): void {
  }

  logout() {
    window.location.href = '/logout';
  }
}
