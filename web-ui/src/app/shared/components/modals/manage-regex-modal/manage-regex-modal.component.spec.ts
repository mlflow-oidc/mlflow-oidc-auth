import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ReactiveFormsModule, FormBuilder, FormControl } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { PermissionEnum, PERMISSIONS } from 'src/app/core/configs/permissions';
import { ManageRegexModalComponent } from './manage-regex-modal.component';
import { ManageRegexModalData } from './manage-regex-modal.interface';

describe('ManageRegexModalComponent', () => {
  let component: ManageRegexModalComponent;
  let fixture: ComponentFixture<ManageRegexModalComponent>;

  function initWithData(data: Partial<ManageRegexModalData>) {
    TestBed.configureTestingModule({
      imports: [ReactiveFormsModule, MatDialogModule],
      declarations: [ManageRegexModalComponent],
      providers: [FormBuilder, { provide: MAT_DIALOG_DATA, useValue: data }],
    }).compileComponents();
    fixture = TestBed.createComponent(ManageRegexModalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('should set title for new regex', () => {
    initWithData({ regex: '', priority: 0, permission: PermissionEnum.READ });
    expect(component.title).toBe('Add New Regex Rule');
  });

  it('should set title for existing regex', () => {
    const existing = 'abc';
    initWithData({ regex: existing, priority: 5, permission: PermissionEnum.MANAGE });
    expect(component.title).toBe(`Manage Regex Rule: ${existing}`);
  });

  it('should initialize form controls with correct defaults and disabled state', () => {
    const existing = 'xyz';
    initWithData({ regex: existing, priority: 7, permission: PermissionEnum.EDIT });
    const form = component.manageRegexForm;
    // regex control disabled and value set
    const regexCtrl = form.get('regex') as FormControl;
    expect(regexCtrl.value).toBe(existing);
    expect(regexCtrl.disabled).toBe(true);
    // priority and permission controls
    expect(form.get('priority')?.value).toBe(7);
    expect(form.get('permission')?.value).toBe(PermissionEnum.EDIT);
    // permissions list assigned
    expect(component.permissions).toEqual(PERMISSIONS);
  });

  it('pythonRegexValidator should return null for valid pattern', () => {
    initWithData({ regex: '', priority: 1, permission: PermissionEnum.READ });
    const valid = component.pythonRegexValidator({ value: '[a-z]+' });
    expect(valid).toBeNull();
  });

  it('pythonRegexValidator should return error for invalid pattern', () => {
    initWithData({ regex: '', priority: 1, permission: PermissionEnum.READ });
    const result = component.pythonRegexValidator({ value: '(*' });
    expect(result).toEqual({ invalidRegex: true });
  });

  it('compareEntities should compare by id when objects provided', () => {
    initWithData({ regex: '', priority: 0, permission: PermissionEnum.READ });
    const obj1 = { id: 1 };
    const obj2 = { id: 1 };
    expect(component.compareEntities(obj1, obj2)).toBe(true);
    expect(component.compareEntities(obj1, { id: 2 })).toBe(false);
  });

  it('compareEntities should fallback to strict equality', () => {
    initWithData({ regex: '', priority: 0, permission: PermissionEnum.READ });
    expect(component.compareEntities(null, null)).toBe(true);
    expect(component.compareEntities('a', 'a')).toBe(true);
    expect(component.compareEntities('a', 'b')).toBe(false);
  });
});
