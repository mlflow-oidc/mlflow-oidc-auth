import { Injectable } from '@angular/core';
import { MatLegacySnackBar as MatSnackBar } from '@angular/material/legacy-snack-bar';
import { CORE_CONFIGS } from '../../../core/configs/core';

@Injectable({
  providedIn: 'root'
})
export class SnackBarService {

  constructor(
    private readonly snackBarService: MatSnackBar,
  ) { }

  openSnackBar(message: string) {
    return this.snackBarService.open(message, 'OK', {
      duration: CORE_CONFIGS.SNACK_BAR_DURATION
    });
  }

}
