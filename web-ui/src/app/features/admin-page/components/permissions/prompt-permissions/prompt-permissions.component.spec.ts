import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PromptPermissionsComponent } from './prompt-permissions.component';

describe('PromptPermissionsComponent', () => {
  let component: PromptPermissionsComponent;
  let fixture: ComponentFixture<PromptPermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ PromptPermissionsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PromptPermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
