import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute } from "@angular/router";
import { of } from "rxjs";
import { provideHttpClient } from "@angular/common/http";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTabsModule } from "@angular/material/tabs";
import { MatIconModule } from "@angular/material/icon";
import { MatDialogModule } from "@angular/material/dialog";

import { UserPermissionsComponent } from "./user-permissions.component";

describe("UserPermissionsComponent", () => {
  let component: UserPermissionsComponent;
  let fixture: ComponentFixture<UserPermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [UserPermissionsComponent],
      imports: [MatProgressSpinnerModule, MatTabsModule, MatIconModule, MatDialogModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({}),
            snapshot: { paramMap: { get: () => null } },
          },
        },
        provideHttpClient(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(UserPermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });
});
