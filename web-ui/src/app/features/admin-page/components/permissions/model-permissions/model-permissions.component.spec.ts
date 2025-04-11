import { provideHttpClient } from "@angular/common/http";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { ActivatedRoute } from "@angular/router";
import { of } from "rxjs";

import { ModelPermissionsComponent } from "./model-permissions.component";

describe("ModelPermissionsComponent", () => {
  let component: ModelPermissionsComponent;
  let fixture: ComponentFixture<ModelPermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ModelPermissionsComponent],
      imports: [MatProgressSpinnerModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: { params: of({}) },
        },
        provideHttpClient(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ModelPermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });
});
