import { TestBed } from '@angular/core/testing';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { HttpClientModule } from '@angular/common/http';
import { ModelRegexDataService } from './model-regex-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';

describe('ModelRegexDataService', () => {
  let service: ModelRegexDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientModule],
      providers: [provideHttpClientTesting(), ModelRegexDataService],
    });
    service = TestBed.inject(ModelRegexDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch model regex permissions for group', () => {
    const groupName = 'group1';
    const mockData = [
      {
        id: '1',
        regex: '.*',
        permission: 'READ',
        priority: 1,
        group_id: 'group1',
        prompt: false,
      },
    ];
    service.getModelRegexPermissionsForGroup(groupName).subscribe((data) => {
      expect(data).toEqual(mockData);
    });
    const req = httpMock.expectOne(
      API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS.replace('${groupName}', groupName)
    );
    expect(req.request.method).toBe('GET');
    req.flush(mockData);
  });

  it('should add model regex permission to group', () => {
    const groupName = 'group1';
    const regex = '.*';
    const permission = 'WRITE';
    const priority = 2;
    service.addModelRegexPermissionToGroup(groupName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({});
    });
    const req = httpMock.expectOne(
      API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS.replace('${groupName}', groupName)
    );
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ regex, priority, permission });
    req.flush({});
  });

  it('should update model regex permission for group', () => {
    const groupName = 'group1';
    const regex = '^test$';
    const permission = 'EDIT';
    const priority = 3;
    const id = '1';
    service.updateModelRegexPermissionForGroup(groupName, regex, permission, priority, id).subscribe((resp) => {
      expect(resp).toEqual({ updated: true });
    });
    const req = httpMock.expectOne(
      API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${patternId}',
        id
      )
    );
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ regex, priority, permission });
    req.flush({ updated: true });
  });

  it('should remove model regex permission from group', () => {
    const groupName = 'group1';
    const id = '1';
    service.removeModelRegexPermissionFromGroup(groupName, id).subscribe((resp) => {
      expect(resp).toEqual({ deleted: true });
    });
    const req = httpMock.expectOne(
      API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${patternId}',
        id
      )
    );
    expect(req.request.method).toBe('DELETE');
    expect(req.request.body).toBeNull();
    req.flush({ deleted: true });
  });
});
