import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { AppComponent } from './app.component';
import { SharedModule } from './shared/shared.module';
import { FooterComponent } from './shared/components/footer/footer.component'; // Import FooterComponent

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        SharedModule, // Keep SharedModule if AppComponent uses other non-standalone items from it
        FooterComponent, // Add standalone FooterComponent here
      ],
      declarations: [AppComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });
});
