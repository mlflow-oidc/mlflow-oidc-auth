import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { ReactiveFormsModule } from '@angular/forms';
import { provideAnimations } from '@angular/platform-browser/animations';

import { GrantUserPermissionsComponent } from './grant-user-permissions.component';

describe('GrantUserPermissionsComponent', () => {
  let component: GrantUserPermissionsComponent;
  let fixture: ComponentFixture<GrantUserPermissionsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [GrantUserPermissionsComponent],
      imports: [MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule, ReactiveFormsModule],
      providers: [{ provide: MAT_DIALOG_DATA, useValue: {} }, provideAnimations()],
    }).compileComponents();

    fixture = TestBed.createComponent(GrantUserPermissionsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
