import { Component, Inject, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { PermissionEnum, PERMISSIONS } from 'src/app/core/configs/permissions';
import { EntityEnum } from 'src/app/core/configs/core';
import { ManageRegexModalData } from './manage-regex-modal.interface';

@Component({
  selector: 'ml-manage-regex-modal',
  templateUrl: './manage-regex-modal.component.html',
  styleUrls: ['./manage-regex-modal.component.scss'],
  standalone: false,
})
export class ManageRegexModalComponent implements OnInit {
  manageRegexForm!: FormGroup;
  permissions = PERMISSIONS;
  entityTypes = [EntityEnum.MODEL, EntityEnum.EXPERIMENT, EntityEnum.PROMPT];
  title: string = '';

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: ManageRegexModalData,
    private readonly fb: FormBuilder
  ) {}

  ngOnInit(): void {
    this.title = `Manage Regex Rule`;
    this.manageRegexForm = this.fb.group({
      entity: [null, Validators.required],
      regex: ['', [Validators.required, this.pythonRegexValidator]],
      priority: [1, [Validators.required, Validators.pattern('^[0-9]+$')]],
      permission: [PermissionEnum.READ, Validators.required],
    });
  }

  pythonRegexValidator(control: any) {
    try {
      // Try to create a RegExp object (JS regex is similar to Python for most cases)
      new RegExp(control.value);
      return null;
    } catch {
      return { invalidRegex: true };
    }
  }

  compareEntities(c1: any, c2: any) {
    return c1 && c2 ? c1.id === c2.id : c1 === c2;
  }
}
