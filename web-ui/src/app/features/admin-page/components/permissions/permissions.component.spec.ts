import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute } from "@angular/router";
import { of } from "rxjs";
import { MatTabsModule } from "@angular/material/tabs";
import { Component } from "@angular/core";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";

import { PermissionsComponent } from "./permissions.component";

@Component({
  selector: "ml-user-permissions",
  template: "<div></div>",
})
class MockMlUserPermissionsComponent {}

@Component({
  selector: "ml-experiment-permissions",
  template: "<div></div>",
})
class MockMlExperimentPermissionsComponent {}

@Component({
  selector: "ml-prompt-permissions",
  template: "<div></div>",
})
class MockMlPromptPermissionsComponent {}

@Component({
  selector: "ml-group-permissions",
  template: "<div></div>",
})
class MockMlGroupPermissionsComponent {}

@Component({
  selector: "ml-model-permissions",
  template: "<div></div>",
})
class MockMlModelPermissionsComponent {}

describe("PermissionsComponent", () => {
  let component: PermissionsComponent;
  let fixture: ComponentFixture<PermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [PermissionsComponent],
      imports: [
        MatTabsModule,
        NoopAnimationsModule,
        MockMlUserPermissionsComponent,
        MockMlExperimentPermissionsComponent,
        MockMlPromptPermissionsComponent,
        MockMlGroupPermissionsComponent,
        MockMlModelPermissionsComponent,
      ],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({}),
            queryParams: of({}),
            snapshot: {
              routeConfig: {
                path: "mock-path",
              },
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });
});
