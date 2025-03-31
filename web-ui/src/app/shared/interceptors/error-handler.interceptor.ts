import { Injectable } from "@angular/core";
import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from "@angular/common/http";
import { catchError, Observable, throwError } from "rxjs";
import { SnackBarService } from "../services";

@Injectable()
export class ErrorHandlerInterceptor implements HttpInterceptor {
  constructor(private readonly snackBarService: SnackBarService) {}

  intercept(
    request: HttpRequest<unknown>,
    next: HttpHandler,
  ): Observable<HttpEvent<unknown>> {
    return next.handle(request).pipe(
      catchError((error: HttpErrorResponse) => {
        let errorMessage =
          error.error instanceof ErrorEvent
            ? `Error: ${error.error.message}`
            : `Error Code: ${error.status}\nMessage: ${error.message}`;

        this.snackBarService.openSnackBar(errorMessage);
        return throwError(() => new Error(errorMessage));
      }),
    );
  }
}
