import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';
import { provideAnimations } from '@angular/platform-browser/animations';

import { TableComponent } from './table.component';

describe('TableComponent', () => {
  let component: TableComponent<string>;
  let fixture: ComponentFixture<TableComponent<string>>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [TableComponent],
      imports: [MatFormFieldModule, MatInputModule, MatTableModule],
      providers: [provideAnimations()],
    }).compileComponents();

    fixture = TestBed.createComponent(TableComponent<string>);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
