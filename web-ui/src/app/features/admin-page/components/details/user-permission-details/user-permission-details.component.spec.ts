import { provideHttpClient } from "@angular/common/http";
import { provideHttpClientTesting } from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatTabsModule } from "@angular/material/tabs";
import { provideAnimations } from "@angular/platform-browser/animations";
import { ActivatedRoute, convertToParamMap } from "@angular/router";
import { of } from "rxjs";
import { UserPermissionDetailsComponent } from "./user-permission-details.component";

describe("UserPermissionDetailsComponent", () => {
  let component: UserPermissionDetailsComponent;
  let fixture: ComponentFixture<UserPermissionDetailsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [UserPermissionDetailsComponent],
      imports: [MatTabsModule],
      providers: [
        provideHttpClientTesting(),
        provideHttpClient(),
        provideAnimations(),
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({ id: "123" }),
            snapshot: {
              paramMap: convertToParamMap({ id: "123" }),
              url: [
                { path: "admin" },
                { path: "details" },
                { path: "permissions" },
              ],
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(UserPermissionDetailsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });
});
