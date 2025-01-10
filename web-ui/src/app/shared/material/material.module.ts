import { NgModule } from '@angular/core';

import { MatLegacyTableModule as MatTableModule } from '@angular/material/legacy-table';
import { MatLegacyFormFieldModule as MatFormFieldModule } from '@angular/material/legacy-form-field';
import { MatLegacyInputModule as MatInputModule } from '@angular/material/legacy-input';
import { MatIconModule } from '@angular/material/icon';
import { MatLegacyButtonModule as MatButtonModule } from '@angular/material/legacy-button';
import { MatLegacyTabsModule as MatTabsModule } from '@angular/material/legacy-tabs';
import { MatLegacyMenuModule as MatMenuModule } from '@angular/material/legacy-menu';
import { MatLegacyDialogModule as MatDialogModule } from '@angular/material/legacy-dialog';
import { MatLegacyProgressSpinnerModule as MatProgressSpinnerModule } from '@angular/material/legacy-progress-spinner';
import { MatLegacySnackBarModule as MatSnackBarModule } from '@angular/material/legacy-snack-bar';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatBadgeModule } from '@angular/material/badge';
import { MatDividerModule } from '@angular/material/divider';

const MATERIAL_MODULES = [
  MatTableModule,
  MatFormFieldModule,
  MatInputModule,
  MatIconModule,
  MatButtonModule,
  MatTabsModule,
  MatMenuModule,
  MatDialogModule,
  MatProgressSpinnerModule,
  MatSnackBarModule,
  MatToolbarModule,
  MatBadgeModule,
  MatDividerModule,
];

@NgModule({
  declarations: [],
  imports: [
    ...MATERIAL_MODULES,
  ],
  exports: [
    ...MATERIAL_MODULES,
  ],
})
export class MaterialModule {}
