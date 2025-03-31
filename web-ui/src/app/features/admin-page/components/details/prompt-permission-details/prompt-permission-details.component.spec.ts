import { provideHttpClient } from "@angular/common/http";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatIconModule } from "@angular/material/icon";
import { ActivatedRoute } from "@angular/router";
import { jest } from "@jest/globals";
import { of } from "rxjs";
import { PromptPermissionDetailsComponent } from "./prompt-permission-details.component";

describe("PromptPermissionDetailsComponent", () => {
  let component: PromptPermissionDetailsComponent;
  let fixture: ComponentFixture<PromptPermissionDetailsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [PromptPermissionDetailsComponent],
      imports: [MatIconModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({ id: "123" }),
            snapshot: {
              data: {},
              paramMap: {
                get: jest.fn((key: string) => (key === "id" ? "123" : null)),
              },
            },
          },
        },
        provideHttpClient(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PromptPermissionDetailsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });
});
