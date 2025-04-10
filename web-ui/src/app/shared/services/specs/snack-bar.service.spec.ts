import { TestBed } from "@angular/core/testing";
import { MatSnackBar } from "@angular/material/snack-bar";
import { CORE_CONFIGS } from "../../../core/configs/core";
import { jest } from "@jest/globals";

import { SnackBarService } from "../utility/snack-bar.service";

describe("SnackBarService", () => {
  let service: SnackBarService;
  let snackBarSpy: { open: jest.Mock };

  beforeEach(() => {
    snackBarSpy = { open: jest.fn() };
    TestBed.configureTestingModule({
      providers: [{ provide: MatSnackBar, useValue: snackBarSpy }],
    });
    service = TestBed.inject(SnackBarService);
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  it("should call MatSnackBar.open with the correct parameters", () => {
    const message = "Test message";
    const action = "OK";
    const duration = CORE_CONFIGS.SNACK_BAR_DURATION;

    service.openSnackBar(message);

    expect(snackBarSpy.open).toHaveBeenCalledWith(message, action, {
      duration,
    });
  });
});
