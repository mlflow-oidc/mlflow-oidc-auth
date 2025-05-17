import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';
import { CurrentUserModel } from '../interfaces/user-data.interface';

describe('AuthService', () => {
  let service: AuthService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(AuthService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should set and get user info correctly', () => {
    const mockUser: CurrentUserModel = {
      id: 1,
      display_name: 'John Doe',
      username: 'john.doe@example.com',
      experiments: [],
      is_admin: false,
      models: [],
      prompts: [],
    };
    service.setUserInfo(mockUser);
    expect(service.getUserInfo()).toEqual(mockUser);
  });
});
