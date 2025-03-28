import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PromptPermissionDetailsComponent } from './prompt-permission-details.component';

describe('PromptPermissionDetailsComponent', () => {
  let component: PromptPermissionDetailsComponent;
  let fixture: ComponentFixture<PromptPermissionDetailsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ PromptPermissionDetailsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PromptPermissionDetailsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
