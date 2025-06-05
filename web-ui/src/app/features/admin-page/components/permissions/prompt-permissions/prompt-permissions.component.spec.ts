import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { ActivatedRoute } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { of } from 'rxjs';

import { PromptPermissionsComponent } from './prompt-permissions.component';

describe('PromptPermissionsComponent', () => {
  let component: PromptPermissionsComponent;
  let fixture: ComponentFixture<PromptPermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [PromptPermissionsComponent],
      imports: [RouterTestingModule, MatProgressSpinnerModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({}),
            queryParams: of({}),
            snapshot: { data: {} },
          },
        },
        provideHttpClient(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PromptPermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
