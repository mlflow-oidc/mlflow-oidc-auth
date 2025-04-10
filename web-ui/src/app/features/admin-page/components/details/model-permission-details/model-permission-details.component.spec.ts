import { provideHttpClient } from "@angular/common/http";
import { CUSTOM_ELEMENTS_SCHEMA } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatIconModule } from "@angular/material/icon";
import { MatTabsModule } from "@angular/material/tabs";
import { provideAnimations } from "@angular/platform-browser/animations";
import { ActivatedRoute } from "@angular/router";
import { of } from "rxjs";

import { ModelPermissionDetailsComponent } from "./model-permission-details.component";

describe("ModelPermissionDetailsComponent", () => {
  let component: ModelPermissionDetailsComponent;
  let fixture: ComponentFixture<ModelPermissionDetailsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ModelPermissionDetailsComponent],
      imports: [MatTabsModule, MatIconModule],
      providers: [
        provideHttpClient(),
        provideAnimations(),
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({ id: "123" }),
            snapshot: { paramMap: { get: () => "123" } },
          },
        },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(ModelPermissionDetailsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });
});
