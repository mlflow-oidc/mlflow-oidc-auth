import { Component, Inject, OnInit } from "@angular/core";
import { FormBuilder, FormGroup, Validators } from "@angular/forms";
import {
  PermissionEnum,
  PERMISSIONS,
} from "../../../../core/configs/permissions";
import { MAT_DIALOG_DATA } from "@angular/material/dialog";

export interface GrantUserPermissionsModel {
  users: string[];
}

@Component({
  selector: "ml-grant-user-permissions",
  templateUrl: "./grant-user-permissions.component.html",
  styleUrls: ["./grant-user-permissions.component.scss"],
  standalone: false,
})
export class GrantUserPermissionsComponent implements OnInit {
  form!: FormGroup;

  permissions = PERMISSIONS;
  title: string = "";

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: GrantUserPermissionsModel,
    private readonly fb: FormBuilder,
  ) {}

  ngOnInit(): void {
    this.title = `Grant permissions`;
    this.form = this.fb.group({
      user: [null, Validators.required],
      permission: [PermissionEnum.READ, Validators.required],
    });
  }
}
