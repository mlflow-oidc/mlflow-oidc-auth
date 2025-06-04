import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { UserDataService } from '../data/user-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { CurrentUserModel, TokenModel } from '../../interfaces/user-data.interface';

describe('UserDataService', () => {
  let service: UserDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [UserDataService],
    });
    service = TestBed.inject(UserDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should return the current user', () => {
    const mockUser: CurrentUserModel = {
      id: 1,
      display_name: 'John Doe',
      username: 'john.doe@example.com',
      experiments: [],
      is_admin: false,
      models: [],
      prompts: [],
    };

    const mockResponse = {
      user: mockUser,
      models: [],
      experiments: [],
      prompts: [],
    };

    service.getCurrentUser().subscribe((response) => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.GET_CURRENT_USER);
    expect(req.request.method).toBe('GET');
    req.flush(mockUser);

    const modelsReq = httpMock.expectOne(API_URL.USER_REGISTERED_MODEL_PERMISSIONS.replace('${userName}', mockUser.username));
    expect(modelsReq.request.method).toBe('GET');
    modelsReq.flush([]);

    const experimentsReq = httpMock.expectOne(API_URL.USER_EXPERIMENT_PERMISSIONS.replace('${userName}', mockUser.username));
    expect(experimentsReq.request.method).toBe('GET');
    experimentsReq.flush([]);

    const promptsReq = httpMock.expectOne(API_URL.USER_PROMPT_PERMISSIONS.replace('${userName}', mockUser.username));
    expect(promptsReq.request.method).toBe('GET');
    promptsReq.flush([]);
  });

  it('should return all users', () => {
    const mockUsers = ['John Doe', 'Jane Smith'];

    service.getAllUsers().subscribe((users) => {
      expect(users).toEqual(mockUsers);
    });

    const req = httpMock.expectOne(API_URL.ALL_USERS);
    expect(req.request.method).toBe('GET');
    req.flush(mockUsers);
  });

  it('should return the user access key for a given username', () => {
    const mockToken: TokenModel = { token: 'mock-user-token' };
    const userName = 'testuser';
    const expirationDate = new Date();
    expirationDate.setFullYear(expirationDate.getFullYear() + 1);

    service.getUserAccessKey(userName, expirationDate).subscribe((token) => {
      expect(token).toEqual(mockToken);
    });

    const req = httpMock.expectOne(API_URL.CREATE_ACCESS_TOKEN);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ username: userName, expiration: expirationDate });
    req.flush(mockToken);
  });

  it('should return all service users', () => {
    const mockServiceUsers = ['ServiceUser1', 'ServiceUser2'];

    service.getAllServiceUsers().subscribe((users) => {
      expect(users).toEqual(mockServiceUsers);
    });

    const req = httpMock.expectOne(`${API_URL.ALL_USERS}?service=true`);
    expect(req.request.method).toBe('GET');
    req.flush(mockServiceUsers);
  });

  it('should create a service account', () => {
    const mockUser = { username: 'service', password: 'pass' };
    const mockResponse = { ...mockUser, id: 123 };

    service.createServiceAccount(mockUser as any).subscribe((user) => {
      expect(user).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.CREATE_USER);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(mockUser);
    req.flush(mockResponse);
  });

  it('should delete a user', () => {
    const mockUser = { username: 'deleteMe' };
    const mockResponse = { ...mockUser, deleted: true };

    service.deleteUser(mockUser as any).subscribe((user) => {
      expect(user).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.DELETE_USER);
    expect(req.request.method).toBe('DELETE');
    expect(req.request.body).toEqual(mockUser);
    req.flush(mockResponse);
  });
});
