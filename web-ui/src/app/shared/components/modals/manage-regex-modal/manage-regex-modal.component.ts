import { Component, Inject, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { PermissionEnum, PERMISSIONS } from 'src/app/core/configs/permissions';
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
  title: string = '';

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: ManageRegexModalData,
    private readonly fb: FormBuilder
  ) {}

  ngOnInit(): void {
    this.title = this.data.regex ? `Manage Regex Rule: ${this.data.regex}` : 'Add New Regex Rule';
    this.manageRegexForm = this.fb.group({
      regex: [
        { value: this.data.regex || '', disabled: !!this.data.regex },
        [Validators.required, this.pythonRegexValidator],
      ],
      priority: [this.data.priority || 1, [Validators.required, Validators.pattern('^[0-9]+$')]],
      permission: [this.data.permission || PermissionEnum.READ, Validators.required],
    });
  }

  pythonRegexValidator(control: any) {
    try {
      new RegExp(control.value);
      return null;
    } catch {
      return { invalidRegex: true };
    }
  }

  compareEntities(c1: any, c2: any) {
    const isObj1 = c1 != null && typeof c1 === 'object' && 'id' in c1;
    const isObj2 = c2 != null && typeof c2 === 'object' && 'id' in c2;
    if (isObj1 && isObj2) {
      return c1.id === c2.id;
    }
    return c1 === c2;
  }
}
