import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { EditPermissionsModalComponent } from './edit-permissions-modal.component';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MatInputModule } from '@angular/material/input';

describe('PermissionsModalComponent', () => {
  let component: EditPermissionsModalComponent;
  let fixture: ComponentFixture<EditPermissionsModalComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [EditPermissionsModalComponent],
      imports: [MatDialogModule, MatFormFieldModule, ReactiveFormsModule, MatInputModule, NoopAnimationsModule],
      providers: [
        { provide: MatDialogRef, useValue: {} },
        { provide: MAT_DIALOG_DATA, useValue: {} },
        provideHttpClientTesting(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(EditPermissionsModalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
