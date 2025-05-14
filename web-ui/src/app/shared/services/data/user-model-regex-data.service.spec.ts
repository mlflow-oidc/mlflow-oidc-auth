import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { UserModelRegexDataService } from './user-model-regex-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { ModelRegexPermissionModel } from '../../interfaces/groups-data.interface';

describe('UserModelRegexDataService', () => {
  let service: UserModelRegexDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [UserModelRegexDataService],
    });
    service = TestBed.inject(UserModelRegexDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch model regex permissions for user', () => {
    const userName = 'user1';
    const mockData: ModelRegexPermissionModel[] = [
      { group_id: 'g1', regex: '.*', permission: PermissionEnum.READ, priority: 1, prompt: false },
    ];
    service.getModelRegexPermissionsForUser(userName).subscribe((data) => {
      expect(data).toEqual(mockData);
    });
    const req = httpMock.expectOne(API_URL.GET_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName));
    expect(req.request.method).toBe('GET');
    req.flush(mockData);
  });

  it('should add model regex permission to user', () => {
    const userName = 'user1';
    const regex = '.*';
    const permission = PermissionEnum.EDIT;
    const priority = 2;
    service.addModelRegexPermissionToUser(userName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({});
    });
    const req = httpMock.expectOne(
      API_URL.CREATE_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName)
    );
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush({});
  });

  it('should update model regex permission for user', () => {
    const userName = 'user1';
    const regex = '^test$';
    const permission = PermissionEnum.MANAGE;
    const priority = 3;
    service.updateModelRegexPermissionForUser(userName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({ updated: true });
    });
    const req = httpMock.expectOne(
      API_URL.UPDATE_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName)
    );
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush({ updated: true });
  });

  it('should remove model regex permission from user', () => {
    const userName = 'user1';
    const regex = 'abc';
    service.removeModelRegexPermissionFromUser(userName, regex).subscribe((resp) => {
      expect(resp).toEqual({ deleted: true });
    });
    const req = httpMock.expectOne(
      API_URL.DELETE_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName)
    );
    expect(req.request.method).toBe('DELETE');
    expect(req.request.body).toEqual({ regex });
    req.flush({ deleted: true });
  });
});
