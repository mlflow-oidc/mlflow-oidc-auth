import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { of, throwError } from 'rxjs';
import { UserDataService } from 'src/app/shared/services/data/user-data.service';

import { AccessKeyModalComponent } from './access-key-modal.component';

describe('AccessKeyModalComponent', () => {
  let component: AccessKeyModalComponent;
  let fixture: ComponentFixture<AccessKeyModalComponent>;
  let userDataServiceMock: Partial<UserDataService>;

  beforeEach(async () => {
    userDataServiceMock = {
      getUserAccessKey: jest.fn(),
    };

    await TestBed.configureTestingModule({
      declarations: [AccessKeyModalComponent],
      imports: [
        MatDialogModule,
        FormsModule,
        ReactiveFormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule,
        MatIconModule,
        MatDatepickerModule,
        MatNativeDateModule,
        BrowserAnimationsModule,
      ],
      providers: [
        { provide: MAT_DIALOG_DATA, useValue: { username: 'testUser' } },
        { provide: UserDataService, useValue: userDataServiceMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AccessKeyModalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should set minDate error if selected date is earlier than today', () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const pastDate = new Date(today.getTime() - 24 * 60 * 60 * 1000); // Yesterday

    component.onDateChange({ value: pastDate } as any);
    expect(component.form.controls['expirationDate'].hasError('minDate')).toBe(true);
  });

  it('should set maxDate error if selected date is later than maxDate', () => {
    const futureDate = new Date(component.maxDate.getTime() + 24 * 60 * 60 * 1000); // Beyond maxDate

    component.onDateChange({ value: futureDate } as any);
    expect(component.form.controls['expirationDate'].hasError('maxDate')).toBe(true);
  });

  it('should call getUserAccessKey and set token on success', () => {
    const mockToken = 'mockToken';
    (userDataServiceMock.getUserAccessKey as jest.Mock).mockReturnValue(of({ token: mockToken }));

    component.requestToken();

    expect(userDataServiceMock.getUserAccessKey).toHaveBeenCalledWith('testUser', expect.any(Date));
    expect(component.token).toBe(mockToken);
  });

  it('should log error if getUserAccessKey fails', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {}); // Mock console.error to prevent actual logging
    (userDataServiceMock.getUserAccessKey as jest.Mock).mockReturnValue(throwError(() => new Error('Error')));

    component.requestToken();

    expect(userDataServiceMock.getUserAccessKey).toHaveBeenCalledWith('testUser', expect.any(Date));
    expect(consoleSpy).toHaveBeenCalledWith('Error generating token for user:', expect.any(Error));

    consoleSpy.mockRestore(); // Restore console.error after the test
  });
});
