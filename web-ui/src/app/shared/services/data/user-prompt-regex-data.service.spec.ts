import { TestBed } from '@angular/core/testing';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { HttpClientModule } from '@angular/common/http';
import { UserPromptRegexDataService } from './user-prompt-regex-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { PromptRegexPermissionModel } from '../../interfaces/groups-data.interface';

describe('UserPromptRegexDataService', () => {
  let service: UserPromptRegexDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientModule],
      providers: [provideHttpClientTesting(), UserPromptRegexDataService],
    });
    service = TestBed.inject(UserPromptRegexDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch prompt regex permissions for user', () => {
    const userName = 'user1';
    const mockData: PromptRegexPermissionModel[] = [
      { group_id: 'g1', regex: '^test$', permission: PermissionEnum.READ, priority: 1, prompt: true },
    ];
    service.getPromptRegexPermissionsForUser(userName).subscribe((data) => {
      expect(data).toEqual(mockData);
    });
    const req = httpMock.expectOne(API_URL.GET_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName));
    expect(req.request.method).toBe('GET');
    req.flush(mockData);
  });

  it('should add prompt regex permission to user', () => {
    const userName = 'user1';
    const regex = '.*';
    const permission = PermissionEnum.EDIT;
    const priority = 2;
    service.addPromptRegexPermissionToUser(userName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({});
    });
    const req = httpMock.expectOne(API_URL.CREATE_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush({});
  });

  it('should update prompt regex permission for user', () => {
    const userName = 'user1';
    const regex = 'abc';
    const permission = PermissionEnum.MANAGE;
    const priority = 3;
    service.updatePromptRegexPermissionForUser(userName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({ updated: true });
    });
    const req = httpMock.expectOne(API_URL.UPDATE_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName));
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush({ updated: true });
  });

  it('should remove prompt regex permission from user', () => {
    const userName = 'user1';
    const regex = 'test123';
    service.removePromptRegexPermissionFromUser(userName, regex).subscribe((resp) => {
      expect(resp).toEqual({ deleted: true });
    });
    const req = httpMock.expectOne(API_URL.DELETE_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName));
    expect(req.request.method).toBe('DELETE');
    expect(req.request.body).toEqual({ regex });
    req.flush({ deleted: true });
  });
});
