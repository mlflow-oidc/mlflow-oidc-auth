import { Component, Inject, OnInit } from "@angular/core";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { FormBuilder, FormGroup, Validators } from "@angular/forms";
import { CreateServiceAccountModalData } from "./create-service-account-modal.interface";

@Component({
    selector: "ml-create-service-account-modal",
    templateUrl: "./create-service-account-modal.component.html",
    styleUrls: ["./create-service-account-modal.component.scss"],
    standalone: false,
})
export class CreateServiceAccountModalComponent implements OnInit {
    public form!: FormGroup;
    title: string = "";

    constructor(
        public dialogRef: MatDialogRef<CreateServiceAccountModalComponent>,
        private readonly fb: FormBuilder,
        @Inject(MAT_DIALOG_DATA) public data: CreateServiceAccountModalData
    ) { }

    ngOnInit(): void {
        this.title = this.data?.title || "Create Service Account";
        this.form = this.fb.group({
            username: [this.data?.username || "", Validators.required],
            display_name: [this.data?.display_name || "", Validators.required],
            is_admin: [this.data?.is_admin || false],
            is_service_account: [true],
        });
    }

    public syncDisplayName(): void {
        const username = this.form.get("username")?.value;
        if (!this.form.get("display_name")?.dirty) {
            this.form.get("display_name")?.setValue(username);
        }
    }

    public submit(): void {
        if (this.form.valid) {
            this.dialogRef.close(this.form.value);
        }
    }

    public close(): void {
        this.dialogRef.close();
    }
}
