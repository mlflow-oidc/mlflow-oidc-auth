import { HTTP_INTERCEPTORS, provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';

import { ErrorHandlerInterceptor } from 'src/app/shared/interceptors/error-handler.interceptor';
import { GroupDataService } from 'src/app/shared/services/data/group-data.service';
import { GroupPermissionsComponent } from './group-permissions.component';

describe('GroupPermissionsComponent', () => {
  let component: GroupPermissionsComponent;
  let fixture: ComponentFixture<GroupPermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MatProgressSpinnerModule],
      declarations: [GroupPermissionsComponent],
      providers: [
        provideHttpClient(),
        GroupDataService,
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({}),
            snapshot: { data: {} },
          },
        },
        {
          provide: HTTP_INTERCEPTORS,
          useClass: ErrorHandlerInterceptor,
          multi: true,
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(GroupPermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
