import { provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';

import { ExperimentPermissionsComponent } from './experiment-permissions.component';

describe('ExperimentPermissionsComponent', () => {
  let component: ExperimentPermissionsComponent;
  let fixture: ComponentFixture<ExperimentPermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ExperimentPermissionsComponent],
      imports: [MatProgressSpinnerModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: { params: of({}) },
        },
        provideHttpClient(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ExperimentPermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
