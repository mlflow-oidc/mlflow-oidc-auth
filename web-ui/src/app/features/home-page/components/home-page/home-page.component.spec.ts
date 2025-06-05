import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ActivatedRoute, UrlSegment } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { of } from 'rxjs';
import { HomePageComponent } from './home-page.component';
import { MatTabsModule } from '@angular/material/tabs';
import { provideAnimations } from '@angular/platform-browser/animations';

describe('HomePageComponent', () => {
  let component: HomePageComponent;
  let fixture: ComponentFixture<HomePageComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RouterTestingModule, MatTabsModule],
      declarations: [HomePageComponent],
      providers: [
        provideHttpClientTesting(),
        provideHttpClient(),
        provideAnimations(),
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({ id: '123' }),
            queryParams: of({ filter: 'test' }),
            snapshot: {
              url: [new UrlSegment('sample-path', {})],
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HomePageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
