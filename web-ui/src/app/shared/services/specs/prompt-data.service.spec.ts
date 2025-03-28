import { TestBed } from '@angular/core/testing';

import { PromptsDataService } from '../data/prompt-data.service';

describe('PromptsDataService', () => {
  let service: PromptsDataService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(PromptsDataService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
