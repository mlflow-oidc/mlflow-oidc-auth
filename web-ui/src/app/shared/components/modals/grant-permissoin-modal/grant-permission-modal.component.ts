import { Component, Inject, OnInit } from '@angular/core';
import { MAT_LEGACY_DIALOG_DATA as MAT_DIALOG_DATA } from '@angular/material/legacy-dialog';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { PermissionEnum, PERMISSIONS } from 'src/app/core/configs/permissions';
import { GrantPermissionModalData } from './grant-permission-modal.inteface';

@Component({
  selector: 'ml-grant-permission-modal',
  templateUrl: './grant-permission-modal.component.html',
  styleUrls: ['./grant-permission-modal.component.scss']
})
export class GrantPermissionModalComponent implements OnInit {
  grantPermissionForm!: FormGroup;

  permissions = PERMISSIONS;
  title: string = '';

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: GrantPermissionModalData,
    private readonly fb: FormBuilder,
  ) {
  }

  ngOnInit(): void {
    this.title = `Grant ${this.data.entityType} permissions for ${this.data.targetName}`;
    this.grantPermissionForm = this.fb.group({
      permission: [PermissionEnum.READ, Validators.required],
      entity: [null, Validators.required],
    })
  }

  compareEntities(c1: any, c2: any) {
    return c1 && c2 ? c1.id === c2.id : c1 === c2;
  }
}
