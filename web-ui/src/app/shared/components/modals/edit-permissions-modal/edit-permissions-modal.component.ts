import { Component, Inject, OnInit } from '@angular/core';
import { MAT_LEGACY_DIALOG_DATA as MAT_DIALOG_DATA, MatLegacyDialogRef as MatDialogRef } from '@angular/material/legacy-dialog';
import { FormBuilder, FormControl, Validators } from '@angular/forms';

import { PERMISSIONS } from 'src/app/core/configs/permissions';
import { PermissionsDialogData } from './edit-permissions-modal.interface';

@Component({
  selector: 'ml-edit-permissions-modal',
  templateUrl: './edit-permissions-modal.component.html',
  styleUrls: ['./edit-permissions-modal.component.scss']
})
export class EditPermissionsModalComponent implements OnInit {
  permissions = PERMISSIONS;
  title: string = '';
  permission: FormControl = new FormControl();

  constructor(
    public dialogRef: MatDialogRef<EditPermissionsModalComponent>,
    @Inject(MAT_DIALOG_DATA) public data: PermissionsDialogData,
    private readonly fb: FormBuilder,
  ) {}

  ngOnInit(): void {
    this.title = `Edit ${this.data.entity} permissions for ${this.data.targetEntity}`;
    this.permission = this.fb.control(this.data.currentPermission, Validators.required);
  }
}
