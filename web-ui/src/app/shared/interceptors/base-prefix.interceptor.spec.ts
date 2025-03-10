import { TestBed } from '@angular/core/testing';

import { BasePrefixInterceptor } from './base-prefix.interceptor';

describe('BasePrefixInterceptor', () => {
  beforeEach(() => TestBed.configureTestingModule({
    providers: [
      BasePrefixInterceptor
      ]
  }));

  it('should be created', () => {
    const interceptor: BasePrefixInterceptor = TestBed.inject(BasePrefixInterceptor);
    expect(interceptor).toBeTruthy();
  });
});
