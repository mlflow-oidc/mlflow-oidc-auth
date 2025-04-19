import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogModule } from '@angular/material/dialog';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { CreateServiceAccountModalComponent } from './create-service-account-modal.component';
import { jest } from '@jest/globals';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTabsModule } from '@angular/material/tabs';
import { MatIconModule } from '@angular/material/icon';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

describe('CreateServiceAccountModalComponent', () => {
    let component: CreateServiceAccountModalComponent;
    let fixture: ComponentFixture<CreateServiceAccountModalComponent>;
    let dialogRefSpy: { close: jest.Mock };

    const data = {
        title: 'Test Title',
        username: 'testuser',
        display_name: 'Test User',
        is_admin: true,
        is_service_account: true,
    };

    beforeEach(async () => {
        dialogRefSpy = { close: jest.fn() };
        await TestBed.configureTestingModule({
            imports: [
                ReactiveFormsModule,
                MatCheckboxModule,
                MatFormFieldModule,
                MatInputModule,
                MatTabsModule,
                MatIconModule,
                MatDialogModule,
                NoopAnimationsModule,
            ],
            declarations: [CreateServiceAccountModalComponent],
            providers: [
                FormBuilder,
                { provide: MatDialogRef, useValue: dialogRefSpy },
                { provide: MAT_DIALOG_DATA, useValue: data },
            ],
        }).compileComponents();
        fixture = TestBed.createComponent(CreateServiceAccountModalComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should initialize form and title from data', () => {
        expect(component.title).toBe(data.title);
        expect(component.form.value.username).toBe(data.username);
        expect(component.form.value.display_name).toBe(data.display_name);
        expect(component.form.value.is_admin).toBe(data.is_admin);
        expect(component.form.value.is_service_account).toBe(true);
    });

    it('should set default title if not provided', async () => {
        const testData = { ...data, title: undefined };
        await TestBed.resetTestingModule()
            .configureTestingModule({
                imports: [
                    ReactiveFormsModule,
                    MatCheckboxModule,
                    MatFormFieldModule,
                    MatInputModule,
                    MatTabsModule,
                    MatIconModule,
                    MatDialogModule,
                    NoopAnimationsModule,
                ],
                declarations: [CreateServiceAccountModalComponent],
                providers: [
                    FormBuilder,
                    { provide: MatDialogRef, useValue: dialogRefSpy },
                    { provide: MAT_DIALOG_DATA, useValue: testData },
                ],
            })
            .compileComponents();
        const testFixture = TestBed.createComponent(CreateServiceAccountModalComponent);
        const testComponent = testFixture.componentInstance;
        testComponent.ngOnInit();
        expect(testComponent.title).toBe('Create Service Account');
    });

    it('should sync display name if not dirty', () => {
        component.form.get('username')?.setValue('newuser');
        component.form.get('display_name')?.markAsPristine();
        component.syncDisplayName();
        expect(component.form.get('display_name')?.value).toBe('newuser');
    });

    it('should not sync display name if dirty', () => {
        component.form.get('username')?.setValue('newuser');
        component.form.get('display_name')?.markAsDirty();
        component.form.get('display_name')?.setValue('dirtyname');
        component.syncDisplayName();
        expect(component.form.get('display_name')?.value).toBe('dirtyname');
    });

    it('should close dialog with form value on submit if form is valid', () => {
        component.form.setValue({
            username: 'user',
            display_name: 'User',
            is_admin: false,
            is_service_account: true,
        });
        component.submit();
        expect(dialogRefSpy.close).toHaveBeenCalledWith(component.form.value);
    });

    it('should not close dialog on submit if form is invalid', () => {
        component.form.get('username')?.setValue('');
        component.submit();
        expect(dialogRefSpy.close).not.toHaveBeenCalled();
    });

    it('should close dialog with no data on close()', () => {
        component.close();
        expect(dialogRefSpy.close).toHaveBeenCalledWith();
    });
});
