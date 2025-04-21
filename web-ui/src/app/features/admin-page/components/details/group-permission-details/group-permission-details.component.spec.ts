import { provideHttpClient } from '@angular/common/http';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { provideAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';

import { GroupPermissionDetailsComponent } from './group-permission-details.component';

describe('GroupPermissionDetailsComponent', () => {
  let component: GroupPermissionDetailsComponent;
  let fixture: ComponentFixture<GroupPermissionDetailsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [GroupPermissionDetailsComponent],
      imports: [MatTabsModule, MatIconModule],
      providers: [
        provideHttpClient(),
        provideAnimations(),
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({ id: '123' }),
            snapshot: {
              paramMap: {
                get: (key: string) => (key === 'id' ? '123' : null),
              },
              url: [{ path: 'user-info' }],
            },
          },
        },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(GroupPermissionDetailsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
