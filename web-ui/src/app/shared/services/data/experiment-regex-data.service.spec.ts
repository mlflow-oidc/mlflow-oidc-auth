import { HttpClientModule } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { ExperimentRegexPermissionModel } from 'src/app/shared/interfaces/groups-data.interface';
import { ExperimentRegexDataService } from './experiment-regex-data.service';
describe('ExperimentRegexDataService', () => {
  let service: ExperimentRegexDataService;
  let httpMock: HttpTestingController;
  const groupName = 'test-group';
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientModule],
      providers: [provideHttpClientTesting(), ExperimentRegexDataService],
    });
    service = TestBed.inject(ExperimentRegexDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    httpMock.verify();
  });
  it('getExperimentRegexPermissionsForGroup should issue GET request and return data', () => {
    const mockResponse: ExperimentRegexPermissionModel[] = [
      { id: '1', group_id: groupName, regex: '.*', permission: PermissionEnum.READ, priority: 0 },
    ];
    service.getExperimentRegexPermissionsForGroup(groupName).subscribe((res) => {
      expect(res).toEqual(mockResponse);
    });
    const req = httpMock.expectOne(API_URL.GROUP_EXPERIMENT_PATTERN_PERMISSIONS.replace('${groupName}', groupName));
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });
  it('addExperimentRegexPermissionToGroup should issue POST request with correct body', () => {
    const regex = '^abc$';
    const permission = 'write';
    const priority = 5;
    const mockResponse = { success: true };
    service.addExperimentRegexPermissionToGroup(groupName, regex, permission, priority).subscribe((res) => {
      expect(res).toEqual(mockResponse);
    });
    const req = httpMock.expectOne(API_URL.GROUP_EXPERIMENT_PATTERN_PERMISSIONS.replace('${groupName}', groupName));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush(mockResponse);
  });
  it('updateExperimentRegexPermissionForGroup should issue PATCH request with correct body', () => {
    const regex = '^xyz$';
    const permission = 'delete';
    const priority = 10;
    const id = '1';
    const mockResponse = { updated: true };
    service.updateExperimentRegexPermissionForGroup(groupName, regex, permission, priority, id).subscribe((res) => {
      expect(res).toEqual(mockResponse);
    });
    const req = httpMock.expectOne(
      API_URL.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL.replace('${groupName}', groupName).replace('${patternId}', id)
    );
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush(mockResponse);
  });
  it('removeExperimentRegexPermissionFromGroup should issue DELETE request', () => {
    const id = '1';
    const mockResponse = { removed: true };
    service.removeExperimentRegexPermissionFromGroup(groupName, id).subscribe((res) => {
      expect(res).toEqual(mockResponse);
    });
    const req = httpMock.expectOne(
      API_URL.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL.replace('${groupName}', groupName).replace('${patternId}', id)
    );
    expect(req.request.method).toBe('DELETE');
    req.flush(mockResponse);
  });
});
