import { Component, Inject, OnInit } from '@angular/core';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { AccessKeyDialogData } from './access-key-modal.interface';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatDatepickerInputEvent } from '@angular/material/datepicker';
import { UserDataService } from 'src/app/shared/services/data/user-data.service';

@Component({
  selector: 'ml-access-key-modal',
  templateUrl: './access-key-modal.component.html',
  styleUrls: ['./access-key-modal.component.scss'],
  standalone: false,
})
export class AccessKeyModalComponent implements OnInit {
  token: string = '';
  form!: FormGroup;
  maxDate: Date;

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: AccessKeyDialogData,
    private fb: FormBuilder,
    private userDataService: UserDataService
  ) {
    this.maxDate = new Date();
    this.maxDate.setFullYear(this.maxDate.getFullYear() + 1);
  }

  ngOnInit(): void {
    const defaultDate = new Date();
    defaultDate.setMonth(defaultDate.getMonth() + 6);

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    this.form = this.fb.group({
      expirationDate: [defaultDate, [Validators.required, Validators.min(today.getTime())]],
    });

    this.form.controls['expirationDate'].setValue(defaultDate);
  }

  onDateChange(event: MatDatepickerInputEvent<Date>): void {
    const selectedDate = event.value;
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (selectedDate && selectedDate < today) {
      this.form.controls['expirationDate'].setErrors({ minDate: true });
    } else if (selectedDate && selectedDate > this.maxDate) {
      this.form.controls['expirationDate'].setErrors({ maxDate: true });
    } else {
      this.form.controls['expirationDate'].setErrors(null);
    }
  }

  requestToken(): void {
    if (this.form.valid) {
      const expirationDate = this.form.value.expirationDate;
      this.userDataService.getUserAccessKey(this.data.username, expirationDate).subscribe({
        next: (response: { token: string }) => {
          this.token = response.token;
        },
        error: (error: any) => {
          console.error('Error generating token for user:', error);
        },
      });
    }
  }

  copyInputMessage(): void {
    navigator.clipboard
      .writeText(this.token)
      .then(() => {})
      .catch((err) => {
        console.error('Failed to copy access key: ', err);
      });
  }
}
