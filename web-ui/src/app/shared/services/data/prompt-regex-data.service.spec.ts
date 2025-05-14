import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { PromptRegexDataService } from './prompt-regex-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';

describe('PromptRegexDataService', () => {
  let service: PromptRegexDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [PromptRegexDataService],
    });
    service = TestBed.inject(PromptRegexDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch prompt regex permissions for group', () => {
    const groupName = 'group1';
    const mockData = [{ regex: '.*', permission: 'READ', priority: 1 }];
    service.getPromptRegexPermissionsForGroup(groupName).subscribe((data) => {
      expect(data).toEqual(mockData);
    });
    const req = httpMock.expectOne(API_URL.GET_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName));
    expect(req.request.method).toBe('GET');
    req.flush(mockData);
  });

  it('should add prompt regex permission to group', () => {
    const groupName = 'group1';
    const regex = '.*';
    const permission = 'WRITE';
    const priority = 2;
    service.addPromptRegexPermissionToGroup(groupName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({});
    });
    const req = httpMock.expectOne(API_URL.CREATE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ regex, priority, permission });
    req.flush({});
  });

  it('should update prompt regex permission for group', () => {
    const groupName = 'group1';
    const regex = '^test$';
    const permission = 'EDIT';
    const priority = 3;
    service.updatePromptRegexPermissionForGroup(groupName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({ updated: true });
    });
    const req = httpMock.expectOne(API_URL.UPDATE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName));
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ regex, priority, permission });
    req.flush({ updated: true });
  });

  it('should remove prompt regex permission from group', () => {
    const groupName = 'group1';
    const regex = '.*';
    service.removePromptRegexPermissionFromGroup(groupName, regex).subscribe((resp) => {
      expect(resp).toEqual({ deleted: true });
    });
    const req = httpMock.expectOne(API_URL.DELETE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName));
    expect(req.request.method).toBe('DELETE');
    expect(req.request.body).toEqual({ regex });
    req.flush({ deleted: true });
  });
});
